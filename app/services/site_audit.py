"""Auditoría masiva de páginas WordPress (lógica interna, sin endpoint propio)."""

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.auditor import run_audit
from app.enums import AnalysisStatus
from app.schemas.analysis import BulkAnalyzeItem
from app.services.scraper import detect_scrape_warning
from app.config import settings
from app.services.wordpress_pages import fetch_wordpress_pages

logger = logging.getLogger(__name__)


def _scrape_warning(analysis) -> str | None:
    scrape = analysis.scrape_result
    if not scrape:
        return None
    return scrape.scrape_warning or detect_scrape_warning(
        scrape.title, scrape.meta_description, scrape.body_text
    )


def audit_wordpress_pages(
    db: Session,
    wordpress_url: str | None = None,
    include_posts: bool = False,
    status: str = "publish",
) -> tuple[str, list[BulkAnalyzeItem], int, int]:
    """
    Scrapea todas las páginas/posts WP y devuelve (source, results, analyzed, failed).
    """
    pages = fetch_wordpress_pages(
        wordpress_url=wordpress_url,
        status=status,
        include_posts=include_posts,
    )
    if not pages:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron páginas en WordPress para analizar.",
        )

    source = (wordpress_url or settings.WORDPRESS_URL or "WORDPRESS_URL (.env)").rstrip("/")
    logger.info("Auditoría masiva WP: %s URLs desde %s", len(pages), source)

    results: list[BulkAnalyzeItem] = []
    analyzed = 0
    failed = 0

    for item in pages:
        try:
            analysis = run_audit(item.url, db)
            db.refresh(analysis, attribute_names=["scrape_result"])
            results.append(
                BulkAnalyzeItem(
                    analysis_id=analysis.id,
                    url=item.url,
                    wp_id=item.wp_id,
                    wp_title=item.title,
                    content_type=item.content_type,
                    seo_score=analysis.seo_score,
                    geo_score=analysis.geo_score,
                    status=AnalysisStatus(analysis.status),
                    scrape_warning=_scrape_warning(analysis),
                )
            )
            analyzed += 1
        except HTTPException as exc:
            failed += 1
            results.append(
                BulkAnalyzeItem(
                    url=item.url,
                    wp_id=item.wp_id,
                    wp_title=item.title,
                    content_type=item.content_type,
                    status=AnalysisStatus.FAILED,
                    error=str(exc.detail),
                )
            )
        except Exception as exc:
            failed += 1
            logger.exception("Fallo audit %s: %s", item.url, exc)
            results.append(
                BulkAnalyzeItem(
                    url=item.url,
                    wp_id=item.wp_id,
                    wp_title=item.title,
                    content_type=item.content_type,
                    status=AnalysisStatus.FAILED,
                    error="Error inesperado durante la auditoría.",
                )
            )

    return source, results, analyzed, failed
