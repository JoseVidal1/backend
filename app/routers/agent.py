import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_full_cycle
from app.agents.recommender import generate_proposals, generate_proposals_for_all
from app.database import get_db
from app.schemas.agent import RunFullCycleRequest, RunFullCycleResponse
from app.schemas.proposal import (
    ProposalSummary,
    RecommendAllRequest,
    RecommendAllResponse,
    RecommendAllResultItem,
    RecommendRequest,
    RecommendResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Recomendar"])


@router.post("/recommend-all", response_model=RecommendAllResponse)
def recommend_all(body: RecommendAllRequest | None = None, db: Session = Depends(get_db)):
    """
    Genera propuestas con Gemini para todos los análisis completados
    (o solo los analysis_ids indicados). Ideal tras POST /analyze/wordpress-pages.
    """
    payload = body or RecommendAllRequest()
    logger.info(
        "POST /agent/recommend-all ids=%s skip_existing=%s",
        payload.analysis_ids,
        payload.skip_existing,
    )
    raw = generate_proposals_for_all(
        db,
        analysis_ids=payload.analysis_ids,
        skip_existing=payload.skip_existing,
    )
    return RecommendAllResponse(
        total_analyses=raw["total_analyses"],
        processed=raw["processed"],
        skipped=raw["skipped"],
        failed=raw["failed"],
        total_proposals_created=raw["total_proposals_created"],
        results=[
            RecommendAllResultItem(
                analysis_id=item["analysis_id"],
                url=item["url"],
                proposals_created=item["proposals_created"],
                proposals=[ProposalSummary.model_validate(p) for p in item["proposals"]],
                skipped=item["skipped"],
                error=item["error"],
            )
            for item in raw["results"]
        ],
    )


@router.post("/recommend", response_model=RecommendResponse)
def recommend(body: RecommendRequest, db: Session = Depends(get_db)):
    """Genera propuestas tipadas con Gemini a partir de un análisis."""
    logger.info("POST /agent/recommend analysis_id=%s", body.analysis_id)
    proposals = generate_proposals(body.analysis_id, db)
    return RecommendResponse(
        analysis_id=body.analysis_id,
        proposals_created=len(proposals),
        proposals=[ProposalSummary.model_validate(p) for p in proposals],
    )


@router.post("/run-full-cycle", response_model=RunFullCycleResponse)
def agent_run_full_cycle(body: RunFullCycleRequest, db: Session = Depends(get_db)):
    """
    Ejecuta en cadena: audit → probe (2 queries) → recommend.
    Ideal para demo end-to-end desde el frontend.
    """
    logger.info("POST /agent/run-full-cycle url=%s", body.url)
    return run_full_cycle(str(body.url), db)
