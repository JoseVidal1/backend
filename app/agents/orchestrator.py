import logging

from sqlalchemy.orm import Session

from app.agents.auditor import run_audit
from app.agents.recommender import generate_proposals
from app.models.gsc_opportunity import GSCOpportunity
from app.models.llm_probe import LLMProbeResult
from app.schemas.agent import RunFullCycleResponse
from app.schemas.analysis import ScrapeSummary
from app.schemas.proposal import ProposalSummary
from app.services.llm_probe import (
    DEFAULT_PROBE_QUERIES,
    probe_data_to_db_fields,
    run_full_probe,
)
from app.services.query_discovery import discover_queries, extract_seeds

logger = logging.getLogger(__name__)

# Demo: 2 queries en ciclo completo (7 tarda demasiado en vivo).
FULL_CYCLE_PROBE_QUERIES = DEFAULT_PROBE_QUERIES[:2]


def _run_query_discovery(scrape_data, db: Session) -> int:
    """
    Descubre queries reales con Google Suggest + DuckDuckGo
    y las guarda como GSCOpportunity en la DB.
    Retorna cuántas queries se guardaron.
    """
    try:
        seeds = extract_seeds(scrape_data)
        discovered = discover_queries(seeds)
        if not discovered:
            logger.info("Query discovery sin resultados — se mantienen las oportunidades existentes.")
            return 0

        # Borramos las oportunidades antiguas y cargamos las nuevas
        # para que el recommender use siempre datos frescos del sitio analizado
        db.query(GSCOpportunity).delete()
        for row in discovered:
            db.add(GSCOpportunity(**row))
        db.commit()

        logger.info("Query discovery: %s oportunidades GSC actualizadas.", len(discovered))
        return len(discovered)
    except Exception as exc:
        # Discovery nunca debe romper el ciclo principal
        logger.warning("Query discovery falló (no crítico): %s", exc)
        return 0


def run_full_cycle(url: str, db: Session) -> RunFullCycleResponse:
    """
    Orquesta audit → query discovery → probe → recommend en una sola llamada.
    """
    logger.info("Ciclo completo iniciado para %s", url)

    analysis = run_audit(url, db)
    db.refresh(analysis, attribute_names=["scrape_result"])

    # Query discovery: seeds reales del scrape → Google Suggest + DDG
    if analysis.scrape_result:
        from app.services.scraper import ScrapeData
        scrape = analysis.scrape_result
        import json
        h2_list = []
        if scrape.h2_list_json:
            try:
                h2_list = json.loads(scrape.h2_list_json)
            except Exception:
                pass
        scrape_data = ScrapeData(
            url=url,
            title=scrape.title or "",
            h1=scrape.h1 or "",
            h2_list=h2_list,
            body_text=scrape.body_text or "",
            word_count=scrape.word_count or 0,
        )
        _run_query_discovery(scrape_data, db)

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


def run_site_cycle(
    db: Session,
    wordpress_url: str | None = None,
    include_posts: bool = True,
    status: str = "publish",
    skip_existing: bool = True,
) -> dict:
    """
    Orquesta audit masivo WordPress → recommend-all en una sola llamada.
    """
    from app.agents.recommender import generate_proposals_for_all
    from app.services.site_audit import audit_wordpress_pages

    logger.info("Ciclo de sitio WP iniciado url=%s include_posts=%s", wordpress_url, include_posts)

    source, audit_results, analyzed, audit_failed = audit_wordpress_pages(
        db,
        wordpress_url=wordpress_url,
        include_posts=include_posts,
        status=status,
    )

    analysis_ids = [r.analysis_id for r in audit_results if r.analysis_id]
    recommend_raw = generate_proposals_for_all(
        db,
        analysis_ids=analysis_ids or None,
        skip_existing=skip_existing,
    )

    logger.info(
        "Ciclo sitio: audit=%s/%s propuestas=%s",
        analyzed,
        len(audit_results),
        recommend_raw["total_proposals_created"],
    )

    return {
        "source": source,
        "total_found": len(audit_results),
        "analyzed": analyzed,
        "audit_failed": audit_failed,
        "audit_results": audit_results,
        "processed": recommend_raw["processed"],
        "skipped": recommend_raw["skipped"],
        "recommend_failed": recommend_raw["failed"],
        "total_proposals_created": recommend_raw["total_proposals_created"],
        "recommend_results": recommend_raw["results"],
    }
