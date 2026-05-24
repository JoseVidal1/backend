import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.enums import AnalysisStatus
from app.models.analysis import Analysis
from app.models.scrape_result import ScrapeResult
from app.services.scorer import calculate_geo_score, calculate_seo_score
from app.services.scraper import scrape

logger = logging.getLogger(__name__)


def run_audit(url: str, db: Session) -> Analysis:
    """
    Orquesta scrape + scores y persiste Analysis + ScrapeResult en la DB.
    """
    analysis = Analysis(url=url, status=AnalysisStatus.PENDING.value)
    db.add(analysis)
    db.flush()

    try:
        scrape_data = scrape(url)
        seo_score = calculate_seo_score(scrape_data)
        geo_score = calculate_geo_score(scrape_data)

        scrape_result = ScrapeResult(
            analysis_id=analysis.id,
            title=scrape_data.title,
            meta_description=scrape_data.meta_description,
            h1=scrape_data.h1,
            h2_list_json=scrape_data.h2_list_as_json(),
            body_text=scrape_data.body_text,
            word_count=scrape_data.word_count,
            has_faq_schema=scrape_data.has_faq_schema,
            has_structured_data=scrape_data.has_structured_data,
            images_without_alt=scrape_data.images_without_alt,
            internal_links_count=scrape_data.internal_links_count,
            scrape_warning=scrape_data.scrape_warning,
        )

        analysis.seo_score = seo_score
        analysis.geo_score = geo_score
        analysis.status = AnalysisStatus.COMPLETED.value
        db.add(scrape_result)
        db.commit()
        db.refresh(analysis)
        if scrape_data.scrape_warning:
            logger.warning("Auditoría id=%s con scrape_warning: %s", analysis.id, scrape_data.scrape_warning)
        logger.info(
            "Auditoría completada id=%s SEO=%s GEO=%s",
            analysis.id,
            seo_score,
            geo_score,
        )
        return analysis

    except HTTPException:
        analysis.status = AnalysisStatus.FAILED.value
        db.commit()
        raise
    except Exception as e:
        analysis.status = AnalysisStatus.FAILED.value
        db.commit()
        logger.exception("Auditoría fallida id=%s: %s", analysis.id, e)
        raise HTTPException(status_code=500, detail="Error inesperado durante la auditoría.")
