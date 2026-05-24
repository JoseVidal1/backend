import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.llm_probe import LLMProbeResult
from app.schemas.probe import ProbeResultItem, ProbeResultListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/probe", tags=["Auditar - LLM Probe"])


@router.get("/results", response_model=ProbeResultListResponse)
def list_probe_results(
    limit: int = 20,
    offset: int = 0,
    analysis_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Historial de LLM probing (generado por run-full-cycle)."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit debe estar entre 1 y 100.")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset no puede ser negativo.")

    query = db.query(LLMProbeResult)
    if analysis_id is not None:
        query = query.filter(LLMProbeResult.analysis_id == analysis_id)

    total = query.count()
    rows = (
        query.order_by(LLMProbeResult.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ProbeResultListResponse(
        items=[ProbeResultItem.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
