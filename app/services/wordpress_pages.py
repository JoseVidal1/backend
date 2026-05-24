"""Obtiene páginas (y opcionalmente entradas) desde la REST API de WordPress."""

import logging
from dataclasses import dataclass

import requests
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class WordPressPageItem:
    wp_id: int
    url: str
    title: str
    content_type: str  # page | post
    status: str


def _wp_auth() -> tuple[str, str] | None:
    if settings.WORDPRESS_USERNAME and settings.WORDPRESS_APP_PASSWORD:
        return (
            settings.WORDPRESS_USERNAME,
            settings.WORDPRESS_APP_PASSWORD.replace(" ", ""),
        )
    return None


def _normalize_wp_base_url(url: str) -> str:
    """
    Acepta URL base del sitio o endpoint REST completo.
    Ej: https://sitio.com/wp-json/wp/v2/pages → https://sitio.com
    """
    cleaned = url.strip().rstrip("/")
    wp_json_idx = cleaned.find("/wp-json")
    if wp_json_idx != -1:
        cleaned = cleaned[:wp_json_idx].rstrip("/")
    return cleaned


def _fetch_paginated(endpoint: str, status: str = "publish") -> list[WordPressPageItem]:
    """Recorre todas las páginas de un endpoint WP REST (pages o posts)."""
    items: list[WordPressPageItem] = []
    page = 1
    auth = _wp_auth()
    content_type = "page" if "/pages" in endpoint else "post"

    while True:
        response = requests.get(
            endpoint,
            params={"per_page": 100, "page": page, "status": status},
            auth=auth,
            timeout=30,
            headers={"Accept": "application/json", "User-Agent": "GEO-Copilot/1.0"},
        )
        if response.status_code == 400 and "rest_post_invalid_page_number" in response.text:
            break
        if response.status_code >= 400:
            logger.error("WordPress pages error %s: %s", response.status_code, response.text[:300])
            hint = ""
            if response.status_code == 404 and "/wp-json/wp-json" in endpoint:
                hint = " Verifica wordpress_url: usa la URL base del sitio, no el endpoint /wp-json/... completo."
            raise HTTPException(
                status_code=502,
                detail=f"No se pudo leer páginas de WordPress ({response.status_code}).{hint}",
            )

        batch = response.json()
        if not batch:
            break

        for row in batch:
            link = row.get("link")
            if not link:
                continue
            title = row.get("title", {}).get("rendered", "") or f"{content_type}-{row.get('id')}"
            items.append(
                WordPressPageItem(
                    wp_id=int(row["id"]),
                    url=link,
                    title=title,
                    content_type=content_type,
                    status=row.get("status", status),
                )
            )

        total_pages = int(response.headers.get("X-WP-TotalPages", 1))
        if page >= total_pages:
            break
        page += 1

    return items


def fetch_wordpress_pages(
    wordpress_url: str | None = None,
    status: str = "publish",
    include_posts: bool = False,
) -> list[WordPressPageItem]:
    """
    Lista todas las páginas publicadas del sitio WordPress.
    Opcionalmente incluye entradas (posts).
    """
    base = _normalize_wp_base_url(wordpress_url or settings.WORDPRESS_URL or "")
    if not base:
        raise HTTPException(
            status_code=400,
            detail="Configura WORDPRESS_URL en .env o envía wordpress_url en el body.",
        )

    pages = _fetch_paginated(f"{base}/wp-json/wp/v2/pages", status=status)
    logger.info("WordPress: %s páginas encontradas en %s", len(pages), base)

    if include_posts:
        posts = _fetch_paginated(f"{base}/wp-json/wp/v2/posts", status=status)
        logger.info("WordPress: %s entradas encontradas en %s", len(posts), base)
        return pages + posts

    return pages
