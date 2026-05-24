import json
import logging
import random
from typing import Protocol

import markdown
import requests
from fastapi import HTTPException

from app.config import settings
from app.enums import ProposalType
from app.services.content_utils import clean_gemini_output

logger = logging.getLogger(__name__)


class WordPressAdapter(Protocol):
    def create_post(self, title: str, content: str) -> dict:
        ...

    def update_meta(self, post_id: int, meta: str) -> dict:
        ...

    def update_alt_text(self, media_id: int, alt: str) -> dict:
        ...


class MockWordPressAdapter:
    """Fallback cuando no hay credenciales WordPress en .env."""

    def create_post(self, title: str, content: str) -> dict:
        post_id = random.randint(1000, 9999)
        slug = title.lower().replace(" ", "-")[:40]
        url = f"https://mock.serfinanza.com/blog/{slug}-{post_id}"
        logger.info("[WP MOCK] create_post id=%s title=%s", post_id, title[:60])
        return {"id": post_id, "url": url, "status": "published"}

    def update_meta(self, post_id: int, meta: str) -> dict:
        url = f"https://mock.serfinanza.com/page/{post_id}"
        logger.info("[WP MOCK] update_meta post_id=%s meta_len=%s", post_id, len(meta))
        return {"id": post_id, "url": url, "status": "published"}

    def update_alt_text(self, media_id: int, alt: str) -> dict:
        url = f"https://mock.serfinanza.com/media/{media_id}"
        logger.info("[WP MOCK] update_alt_text media_id=%s alt=%s", media_id, alt[:60])
        return {"id": media_id, "url": url, "status": "published"}


class WordPressRestAdapter:
    """Publica en WordPress real vía REST API (Application Passwords)."""

    def __init__(
        self,
        base_url: str,
        username: str,
        app_password: str,
        post_status: str = "draft",
        meta_post_id: int | None = None,
    ):
        self.api_base = f"{base_url.rstrip('/')}/wp-json/wp/v2"
        self.auth = (username, app_password.replace(" ", ""))
        self.post_status = post_status
        self.meta_post_id = meta_post_id

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self.api_base}{path}"
        try:
            response = requests.request(
                method,
                url,
                json=payload,
                auth=self.auth,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code >= 400:
                logger.error("WordPress error %s: %s", response.status_code, response.text[:300])
                raise HTTPException(
                    status_code=502,
                    detail=f"WordPress respondió {response.status_code}. Revisa URL, usuario y Application Password.",
                )
            return response.json()
        except HTTPException:
            raise
        except requests.RequestException as exc:
            logger.error("WordPress request falló: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="No se pudo conectar a WordPress. Verifica WORDPRESS_URL en .env.",
            ) from exc

    @staticmethod
    def _markdown_to_html(content: str) -> str:
        cleaned = clean_gemini_output(content)
        return markdown.markdown(cleaned, extensions=["extra", "nl2br"])

    @staticmethod
    def _json_to_html(content: str) -> str:
        cleaned = clean_gemini_output(content)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return f"<pre>{cleaned}</pre>"

        if "faqs" in data:
            parts = ["<h2>Preguntas frecuentes</h2>"]
            for item in data["faqs"]:
                parts.append(f"<h3>{item.get('question', '')}</h3>")
                parts.append(f"<p>{item.get('answer', '')}</p>")
            return "\n".join(parts)

        if "alt_texts" in data:
            parts = ["<h2>Textos alt sugeridos</h2>", "<ul>"]
            for item in data["alt_texts"]:
                img = item.get("suggested_image", "imagen")
                alt = item.get("alt_text", "")
                parts.append(f"<li><strong>{img}</strong>: {alt}</li>")
            parts.append("</ul>")
            return "\n".join(parts)

        return f"<pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre>"

    def create_post(self, title: str, content: str) -> dict:
        cleaned = clean_gemini_output(content)
        if cleaned.lstrip().startswith(("{", "[")):
            html = self._json_to_html(cleaned)
        else:
            html = self._markdown_to_html(cleaned)

        post = self._request(
            "POST",
            "/posts",
            {
                "title": title,
                "content": html,
                "status": self.post_status,
            },
        )
        logger.info("[WP REAL] Post creado id=%s url=%s", post.get("id"), post.get("link"))
        return {
            "id": post.get("id"),
            "url": post.get("link"),
            "status": post.get("status"),
        }

    def update_meta(self, post_id: int, meta: str) -> dict:
        target_id = self.meta_post_id or post_id
        meta_clean = clean_gemini_output(meta)
        post = self._request(
            "POST",
            f"/posts/{target_id}",
            {"excerpt": meta_clean[:160]},
        )
        logger.info("[WP REAL] Meta/excerpt actualizado post_id=%s", target_id)
        return {
            "id": post.get("id"),
            "url": post.get("link"),
            "status": post.get("status"),
        }

    def update_alt_text(self, media_id: int, alt: str) -> dict:
        cleaned = clean_gemini_output(alt)
        try:
            data = json.loads(cleaned)
            alt_texts = data.get("alt_texts", [])
            if alt_texts:
                cleaned = alt_texts[0].get("alt_text", cleaned)
        except json.JSONDecodeError:
            pass

        media = self._request(
            "POST",
            f"/media/{media_id}",
            {"alt_text": cleaned[:500]},
        )
        logger.info("[WP REAL] Alt text actualizado media_id=%s", media_id)
        return {
            "id": media.get("id"),
            "url": media.get("source_url") or media.get("link"),
            "status": "updated",
        }


def get_wordpress_adapter() -> WordPressAdapter:
    """Usa WordPress real si hay credenciales; si no, mock."""
    if (
        settings.WORDPRESS_URL
        and settings.WORDPRESS_USERNAME
        and settings.WORDPRESS_APP_PASSWORD
    ):
        logger.info("WordPress adapter: REST real → %s", settings.WORDPRESS_URL)
        return WordPressRestAdapter(
            base_url=settings.WORDPRESS_URL,
            username=settings.WORDPRESS_USERNAME,
            app_password=settings.WORDPRESS_APP_PASSWORD,
            post_status=settings.WORDPRESS_POST_STATUS,
            meta_post_id=settings.WORDPRESS_META_POST_ID,
        )

    logger.info("WordPress adapter: MOCK (faltan credenciales en .env)")
    return MockWordPressAdapter()


def publish_proposal(
    proposal_type: str,
    title: str,
    content: str | None,
    adapter: WordPressAdapter | None = None,
) -> dict:
    wp: WordPressAdapter = adapter or get_wordpress_adapter()
    body = clean_gemini_output(content or "")

    if proposal_type == ProposalType.BLOG_POST.value:
        return wp.create_post(title, body)

    if proposal_type == ProposalType.META_DESCRIPTION.value:
        post_id = settings.WORDPRESS_META_POST_ID or 1
        return wp.update_meta(post_id=post_id, meta=body)

    if proposal_type == ProposalType.FAQ_SCHEMA.value:
        return wp.create_post(f"FAQ — {title}", body)

    if proposal_type == ProposalType.SCHEMA_MARKUP.value:
        post_id = settings.WORDPRESS_META_POST_ID or 1
        return wp.update_meta(post_id=post_id, meta=body)

    if proposal_type == ProposalType.ALT_TEXT_FIX.value:
        media_id = settings.WORDPRESS_DEFAULT_MEDIA_ID or 1
        return wp.update_alt_text(media_id=media_id, alt=body)

    if proposal_type == ProposalType.GEO_INSIGHT.value:
        return wp.create_post(f"Insight GEO — {title}", body)

    raise ValueError(f"Tipo de propuesta no publicable: {proposal_type}")
