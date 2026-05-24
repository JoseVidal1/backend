import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis import Analysis
from app.models.llm_probe import LLMProbeResult
from app.schemas.probe import ProbeResultItem, ProbeResultListResponse, ProbeRunRequest, ProbeRunResponse
from app.services.llm_probe import DEFAULT_PROBE_QUERIES, probe_data_to_db_fields, run_full_probe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/probe", tags=["Auditar - LLM Probe"])


@router.post("/run", response_model=ProbeRunResponse)
def run_probe(body: ProbeRunRequest | None = None, db: Session = Depends(get_db)):
    """
    Ejecuta LLM probing: pregunta queries financieras a Gemini y mide
    si menciona Serfinanza vs competidores.
    """
    payload = body or ProbeRunRequest()
    queries = payload.queries or DEFAULT_PROBE_QUERIES

    if not queries:
        raise HTTPException(status_code=400, detail="Debes enviar al menos una query.")

    if payload.analysis_id is not None:
        analysis = db.get(Analysis, payload.analysis_id)
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail=f"No existe análisis con id {payload.analysis_id}.",
            )

    logger.info("Ejecutando probe para %s queries", len(queries))
    probe_results = run_full_probe(queries=queries)

    saved: list[LLMProbeResult] = []
    for item in probe_results:
        row = LLMProbeResult(
            analysis_id=payload.analysis_id,
            **probe_data_to_db_fields(item),
        )
        db.add(row)
        saved.append(row)

    db.commit()
    for row in saved:
        db.refresh(row)

    return ProbeRunResponse(
        results=[ProbeResultItem.model_validate(r) for r in saved],
        total=len(saved),
    )


@router.get("/results", response_model=ProbeResultListResponse)
def list_probe_results(
    limit: int = 20,
    offset: int = 0,
    analysis_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Lista histórica de resultados de LLM probing."""
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
