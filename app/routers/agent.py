import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_full_cycle
from app.agents.recommender import generate_proposals
from app.database import get_db
from app.schemas.agent import RunFullCycleRequest, RunFullCycleResponse
from app.schemas.proposal import ProposalSummary, RecommendRequest, RecommendResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Recomendar"])


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
