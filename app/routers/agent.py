import logging
import threading

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_full_cycle, run_site_cycle
from app.database import SessionLocal, get_db
from app.schemas.agent import (
    RunFullCycleRequest,
    RunFullCycleResponse,
    RunSiteCycleRequest,
    RunSiteCycleResponse,
)
from app.schemas.proposal import ProposalSummary, RecommendAllResultItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agente"])

# Estado global del ciclo async
_cycle_status: dict = {"running": False, "last_result": None, "last_error": None}


@router.post("/run-full-cycle", response_model=RunFullCycleResponse)
def agent_run_full_cycle(body: RunFullCycleRequest, db: Session = Depends(get_db)):
    """
    **Una URL:** scrape + SEO/GEO score + LLM probe (2 queries) + propuestas Gemini.
    """
    logger.info("POST /agent/run-full-cycle url=%s", body.url)
    return run_full_cycle(str(body.url), db)


@router.post("/trigger", status_code=202)
def agent_trigger(body: RunFullCycleRequest):
    """
    Audita UNA sola URL en background y devuelve 202 inmediatamente.
    Polling: GET /agent/trigger/status

    Skip-if-recent: si ya hay análisis completado en los últimos 30 min
    para esa URL, omite el ciclo para no agotar la cuota de Gemini.
    """
    global _cycle_status

    if _cycle_status["running"]:
        return {"status": "running", "message": "Ya hay un ciclo en ejecución."}

    url = str(body.url)

    # ── Skip-if-recent ───────────────────────────────────────────────────────
    from datetime import datetime, timedelta
    from app.models.analysis import Analysis
    from app.enums import AnalysisStatus

    _skip_db = SessionLocal()
    try:
        threshold = datetime.now() - timedelta(minutes=30)
        recent = (
            _skip_db.query(Analysis)
            .filter(
                Analysis.url == url,
                Analysis.status == AnalysisStatus.COMPLETED.value,
                Analysis.created_at >= threshold,
            )
            .first()
        )
        if recent:
            age_min = int((datetime.now() - recent.created_at).total_seconds() / 60)
            logger.info("[Trigger] Skip — análisis reciente id=%s (%s min) para %s", recent.id, age_min, url)
            return {
                "status": "skipped",
                "message": f"Análisis reciente encontrado (hace {age_min} min). Espera 30 min o usa /agent/run-full-cycle para forzar.",
            }
    finally:
        _skip_db.close()

    def _run():
        global _cycle_status
        _cycle_status["running"] = True
        _cycle_status["last_error"] = None
        db = SessionLocal()
        try:
            result = run_full_cycle(url, db)
            _cycle_status["last_result"] = {
                "analyzed": 1,
                "total_proposals_created": result.proposals_count,
            }
            logger.info("[Trigger] Ciclo completado url=%s propuestas=%s", url, result.proposals_count)
        except Exception as exc:
            _cycle_status["last_error"] = str(exc)
            logger.error("[Trigger] Ciclo falló url=%s: %s", url, exc)
        finally:
            _cycle_status["running"] = False
            db.close()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "message": f"Ciclo iniciado para {url}. Polling a /agent/trigger/status"}


@router.get("/trigger/status")
def agent_trigger_status():
    """Devuelve el estado actual del ciclo async."""
    return {
        "running": _cycle_status["running"],
        "last_result": _cycle_status["last_result"],
        "last_error": _cycle_status["last_error"],
    }


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
