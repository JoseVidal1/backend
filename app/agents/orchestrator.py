import logging

from sqlalchemy.orm import Session

from app.agents.auditor import run_audit
from app.agents.recommender import generate_proposals
from app.models.llm_probe import LLMProbeResult
from app.schemas.agent import RunFullCycleResponse
from app.schemas.analysis import ScrapeSummary
from app.schemas.proposal import ProposalSummary
from app.services.llm_probe import (
    DEFAULT_PROBE_QUERIES,
    probe_data_to_db_fields,
    run_full_probe,
)

logger = logging.getLogger(__name__)

# Demo: 2 queries en ciclo completo (7 tarda demasiado en vivo).
FULL_CYCLE_PROBE_QUERIES = DEFAULT_PROBE_QUERIES[:2]


def run_full_cycle(url: str, db: Session) -> RunFullCycleResponse:
    """
    Orquesta audit → probe → recommend en una sola llamada.
    """
    logger.info("Ciclo completo iniciado para %s", url)

    analysis = run_audit(url, db)
    db.refresh(analysis, attribute_names=["scrape_result"])

    probe_data_list = run_full_probe(queries=FULL_CYCLE_PROBE_QUERIES)
    for item in probe_data_list:
        db.add(
            LLMProbeResult(
                analysis_id=analysis.id,
                **probe_data_to_db_fields(item),
            )
        )
    db.commit()

    proposals = generate_proposals(analysis.id, db)

    scrape = analysis.scrape_result
    scrape_summary = None
    if scrape:
        scrape_summary = ScrapeSummary(
            title=scrape.title,
            meta_description=scrape.meta_description,
            h1=scrape.h1,
            word_count=scrape.word_count or 0,
            has_faq_schema=bool(scrape.has_faq_schema),
            has_structured_data=bool(scrape.has_structured_data),
            internal_links_count=scrape.internal_links_count or 0,
            images_without_alt=scrape.images_without_alt or 0,
            scrape_warning=scrape.scrape_warning,
        )

    logger.info(
        "Ciclo completo id=%s probes=%s propuestas=%s",
        analysis.id,
        len(probe_data_list),
        len(proposals),
    )

    return RunFullCycleResponse(
        analysis_id=analysis.id,
        url=analysis.url,
        seo_score=analysis.seo_score,
        geo_score=analysis.geo_score,
        probe_results_count=len(probe_data_list),
        proposals_count=len(proposals),
        scrape_summary=scrape_summary,
        scrape_warning=scrape.scrape_warning if scrape else None,
        proposals=[ProposalSummary.model_validate(p) for p in proposals],
    )
