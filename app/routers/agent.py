import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_full_cycle, run_site_cycle
from app.database import get_db
from app.schemas.agent import (
    RunFullCycleRequest,
    RunFullCycleResponse,
    RunSiteCycleRequest,
    RunSiteCycleResponse,
)
from app.schemas.proposal import ProposalSummary, RecommendAllResultItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agente"])


@router.post("/run-full-cycle", response_model=RunFullCycleResponse)
def agent_run_full_cycle(body: RunFullCycleRequest, db: Session = Depends(get_db)):
    """
    **Una URL:** scrape + SEO/GEO score + LLM probe (2 queries) + propuestas Gemini.
    """
    logger.info("POST /agent/run-full-cycle url=%s", body.url)
    return run_full_cycle(str(body.url), db)


@router.post("/run-site-cycle", response_model=RunSiteCycleResponse)
def agent_run_site_cycle(body: RunSiteCycleRequest | None = None, db: Session = Depends(get_db)):
    """
    **Sitio WordPress completo:** audita todas las páginas/posts vía REST API
    y genera propuestas para cada una en una sola llamada.
    """
    payload = body or RunSiteCycleRequest()
    wp_url = str(payload.wordpress_url) if payload.wordpress_url else None
    logger.info("POST /agent/run-site-cycle url=%s", wp_url)

    raw = run_site_cycle(
        db,
        wordpress_url=wp_url,
        include_posts=payload.include_posts,
        status=payload.status,
        skip_existing=payload.skip_existing,
    )

    return RunSiteCycleResponse(
        source=raw["source"],
        total_found=raw["total_found"],
        analyzed=raw["analyzed"],
        audit_failed=raw["audit_failed"],
        audit_results=raw["audit_results"],
        processed=raw["processed"],
        skipped=raw["skipped"],
        recommend_failed=raw["recommend_failed"],
        total_proposals_created=raw["total_proposals_created"],
        recommend_results=[
            RecommendAllResultItem(
                analysis_id=item["analysis_id"],
                url=item["url"],
                proposals_created=item["proposals_created"],
                proposals=[ProposalSummary.model_validate(p) for p in item["proposals"]],
                skipped=item["skipped"],
                error=item["error"],
            )
            for item in raw["recommend_results"]
        ],
    )
