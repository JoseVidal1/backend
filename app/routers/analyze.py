import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.enums import AnalysisStatus
from app.models.analysis import Analysis
from app.schemas.analysis import AnalysisDetail, AnalysisListResponse, AnalysisSummary
from app.schemas.probe import ProbeResultItem
from app.schemas.proposal import ProposalSummary
from app.database import get_db
from app.services.scraper import detect_scrape_warning

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Auditar"])


def _analysis_scrape_warning(analysis: Analysis) -> str | None:
    scrape = analysis.scrape_result
    if not scrape:
        return None
    return scrape.scrape_warning or detect_scrape_warning(
        scrape.title, scrape.meta_description, scrape.body_text
    )


@router.get("/analyses", response_model=AnalysisListResponse)
def list_analyses(
    status: AnalysisStatus | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Lista análisis previos (generados por run-full-cycle o run-site-cycle).

    **status** = estado del scrape: `completed` | `failed`. Evitar `pending` (casi siempre vacío).
    """
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
    """Detalle de un análisis con scrape, probe y propuestas."""
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
