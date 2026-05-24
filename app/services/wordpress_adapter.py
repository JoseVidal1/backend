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
from app.services.html_styler import apply_inline_styles

logger = logging.getLogger(__name__)

_PATCH_MARKER = "<!-- geo-copilot-patch -->"


class WordPressAdapter(Protocol):
    def create_post(self, title: str, content: str) -> dict:
        ...

    def update_meta(self, post_id: int, meta: str) -> dict:
        ...

    def update_alt_text(self, media_id: int, alt: str) -> dict:
        ...

    def append_to_post(self, post_id: int, html_fragment: str) -> dict:
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
        return {"id": media_id, "url": url, "status": "updated"}

    def append_to_post(self, post_id: int, html_fragment: str) -> dict:
        url = f"https://mock.serfinanza.com/page/{post_id}"
        logger.info("[WP MOCK] append_to_post post_id=%s fragment_len=%s", post_id, len(html_fragment))
        return {"id": post_id, "url": url, "status": "updated"}


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
        html = markdown.markdown(cleaned, extensions=["extra", "nl2br"])
        return apply_inline_styles(html)

    @staticmethod
    def _json_to_html(content: str, proposal_type: ProposalType | None = None) -> str:
        cleaned = clean_gemini_output(content)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return apply_inline_styles(f"<pre>{cleaned}</pre>")

        if "faqs" in data:
            parts = [
                f'<section style="margin-top: 32px;">{_PATCH_MARKER}',
                '<h2 style="font-family: Segoe UI, Georgia, serif; color: #004080; '
                'font-size: 22px; border-bottom: 2px solid #0066cc; padding-bottom: 6px;">'
                "Preguntas frecuentes</h2>",
            ]
            for item in data["faqs"]:
                q = item.get("question", "")
                a = item.get("answer", "")
                parts.append(
                    f'<h3 style="font-family: Segoe UI, Georgia, serif; color: #005599; '
                    f'font-size: 18px; margin: 16px 0 8px;">{q}</h3>'
                )
                parts.append(
                    f'<p style="font-family: Segoe UI, Arial, sans-serif; color: #333; '
                    f'font-size: 16px; line-height: 1.7; margin: 0 0 14px;">{a}</p>'
                )
            parts.append("</section>")
            return apply_inline_styles("\n".join(parts), wrap=False)

        if "alt_texts" in data:
            parts = [
                "<h2>Textos alt sugeridos</h2>",
                '<ul style="font-family: Segoe UI, Arial, sans-serif; color: #333; line-height: 1.7;">',
            ]
            for item in data["alt_texts"]:
                img = item.get("suggested_image", "imagen")
                alt = item.get("alt_text", "")
                parts.append(f"<li><strong>{img}</strong>: {alt}</li>")
            parts.append("</ul>")
            return apply_inline_styles("\n".join(parts))

        if proposal_type == ProposalType.GEO_INSIGHT and all(k in data for k in ("problem", "impact", "recommendation")):
            parts = [
                f'<section style="margin-top: 32px;">{_PATCH_MARKER}',
                '<h2 style="color: #004080; font-size: 22px;">Insight GEO</h2>',
                f'<p style="color: #333; line-height: 1.7;"><strong>Problema:</strong> {data["problem"]}</p>',
                f'<p style="color: #333; line-height: 1.7;"><strong>Impacto:</strong> {data["impact"]}</p>',
                f'<p style="color: #333; line-height: 1.7;"><strong>Recomendación:</strong> {data["recommendation"]}</p>',
                "</section>",
            ]
            return apply_inline_styles("\n".join(parts), wrap=False)

        return apply_inline_styles(f"<pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre>")

    @staticmethod
    def _schema_to_script(content: str) -> str:
        cleaned = clean_gemini_output(content)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = {"description": cleaned}
        json_ld = json.dumps(data, ensure_ascii=False)
        return (
            f'{_PATCH_MARKER}\n'
            f'<script type="application/ld+json">{json_ld}</script>'
        )

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

    def append_to_post(self, post_id: int, html_fragment: str) -> dict:
        """Agrega HTML al final del post existente sin reemplazar el contenido."""
        existing = self._request("GET", f"/posts/{post_id}?context=edit")
        current = existing.get("content", {}).get("raw") or existing.get("content", {}).get("rendered") or ""
        updated = f"{current.rstrip()}\n\n{html_fragment}"
        post = self._request(
            "POST",
            f"/posts/{post_id}",
            {"content": updated},
        )
        logger.info("[WP REAL] Fragmento agregado a post_id=%s", post_id)
        return {
            "id": post.get("id"),
            "url": post.get("link"),
            "status": post.get("status"),
        }

    def update_meta(self, post_id: int, meta: str) -> dict:
        meta_clean = clean_gemini_output(meta)
        post = self._request(
            "POST",
            f"/posts/{post_id}",
            {"excerpt": meta_clean[:160]},
        )
        logger.info("[WP REAL] Meta/excerpt actualizado post_id=%s", post_id)
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


def _target_post_id() -> int:
    return settings.WORDPRESS_META_POST_ID or 1


def publish_proposal(
    proposal_type: str,
    title: str,
    content: str | None,
    adapter: WordPressAdapter | None = None,
) -> dict:
    """
    Publica según tipo:
    - Parches (meta, FAQ, schema, insight): modifican el post existente.
    - Blog: crea entrada nueva con estilos inline.
    - Alt text: solo actualiza media.
    """
    wp: WordPressAdapter = adapter or get_wordpress_adapter()
    body = clean_gemini_output(content or "")
    ptype = ProposalType(proposal_type)
    target_post = _target_post_id()

    if ptype == ProposalType.BLOG_POST:
        return wp.create_post(title, body)

    if ptype == ProposalType.META_DESCRIPTION:
        return wp.update_meta(post_id=target_post, meta=body)

    if ptype == ProposalType.FAQ_SCHEMA:
        html = WordPressRestAdapter._json_to_html(body, ProposalType.FAQ_SCHEMA)
        return wp.append_to_post(post_id=target_post, html_fragment=html)

    if ptype == ProposalType.SCHEMA_MARKUP:
        script = WordPressRestAdapter._schema_to_script(body)
        return wp.append_to_post(post_id=target_post, html_fragment=script)

    if ptype == ProposalType.ALT_TEXT_FIX:
        media_id = settings.WORDPRESS_DEFAULT_MEDIA_ID or 1
        return wp.update_alt_text(media_id=media_id, alt=body)

    if ptype == ProposalType.GEO_INSIGHT:
        html = WordPressRestAdapter._json_to_html(body, ProposalType.GEO_INSIGHT)
        return wp.append_to_post(post_id=target_post, html_fragment=html)

    raise ValueError(f"Tipo de propuesta no publicable: {proposal_type}")
