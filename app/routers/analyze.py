import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.agents.auditor import run_audit
from app.enums import AnalysisStatus
from app.models.analysis import Analysis
from app.schemas.analysis import (
    AnalysisDetail,
    AnalysisListResponse,
    AnalysisSummary,
    AnalyzeRequest,
    AnalyzeResponse,
    ScrapeSummary,
)
from app.schemas.probe import ProbeResultItem
from app.schemas.proposal import ProposalSummary
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Auditar"])


from app.services.scraper import detect_scrape_warning


def _scrape_summary_from_analysis(analysis: Analysis) -> ScrapeSummary | None:
    scrape = analysis.scrape_result
    if not scrape:
        return None
    warning = scrape.scrape_warning or detect_scrape_warning(
        scrape.title, scrape.meta_description, scrape.body_text
    )
    return ScrapeSummary(
        title=scrape.title,
        meta_description=scrape.meta_description,
        h1=scrape.h1,
        word_count=scrape.word_count or 0,
        has_faq_schema=bool(scrape.has_faq_schema),
        has_structured_data=bool(scrape.has_structured_data),
        internal_links_count=scrape.internal_links_count or 0,
        images_without_alt=scrape.images_without_alt or 0,
        scrape_warning=warning,
    )


def _analysis_scrape_warning(analysis: Analysis) -> str | None:
    scrape = analysis.scrape_result
    if not scrape:
        return None
    return scrape.scrape_warning or detect_scrape_warning(
        scrape.title, scrape.meta_description, scrape.body_text
    )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_url(body: AnalyzeRequest, db: Session = Depends(get_db)):
    """Scrapea una URL, calcula SEO/GEO Score y guarda el análisis."""
    url = str(body.url)
    logger.info("POST /analyze url=%s", url)
    analysis = run_audit(url, db)
    db.refresh(analysis, attribute_names=["scrape_result"])

    return AnalyzeResponse(
        analysis_id=analysis.id,
        url=analysis.url,
        seo_score=analysis.seo_score,
        geo_score=analysis.geo_score,
        status=AnalysisStatus(analysis.status),
        scrape_summary=_scrape_summary_from_analysis(analysis),
        scrape_warning=_analysis_scrape_warning(analysis),
    )


@router.get("/analyses", response_model=AnalysisListResponse)
def list_analyses(
    status: AnalysisStatus | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Lista análisis previos con paginación."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit debe estar entre 1 y 100.")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset no puede ser negativo.")

    query = db.query(Analysis)
    if status is not None:
        query = query.filter(Analysis.status == status.value)

    total = query.count()
    rows = (
        query.order_by(Analysis.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return AnalysisListResponse(
        items=[AnalysisSummary.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """Detalle completo de un análisis con scrape, probe y propuestas."""
    analysis = (
        db.query(Analysis)
        .options(
            joinedload(Analysis.scrape_result),
            joinedload(Analysis.llm_probe_results),
            joinedload(Analysis.proposals),
        )
        .filter(Analysis.id == analysis_id)
        .one_or_none()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail=f"No existe análisis con id {analysis_id}.")

    from app.schemas.analysis import ScrapeResultDetail

    return AnalysisDetail(
        id=analysis.id,
        url=analysis.url,
        seo_score=analysis.seo_score,
        geo_score=analysis.geo_score,
        status=AnalysisStatus(analysis.status),
        created_at=analysis.created_at,
        scrape_warning=_analysis_scrape_warning(analysis),
        scrape_result=(
            ScrapeResultDetail.model_validate(analysis.scrape_result)
            if analysis.scrape_result
            else None
        ),
        probe_results=[ProbeResultItem.model_validate(p) for p in analysis.llm_probe_results],
        proposals=[ProposalSummary.model_validate(p) for p in analysis.proposals],
    )
