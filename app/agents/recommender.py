import json
import logging
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.enums import AnalysisStatus, ProposalStatus, ProposalType, Severity, TriggerSource
from app.models.analysis import Analysis
from app.models.gsc_opportunity import GSCOpportunity
from app.models.llm_probe import LLMProbeResult
from app.models.proposal import Proposal
from app.models.scrape_result import ScrapeResult
from app.prompts import templates
from app.services.feedback_learning import get_rejection_learnings
from app.services.gemini_client import GeminiClient, get_gemini_client

logger = logging.getLogger(__name__)

MAX_PROBE_BLOGS = 2


@dataclass
class ProposalPlan:
    proposal_type: ProposalType
    title: str
    summary: str
    severity: Severity
    trigger_source: TriggerSource
    trigger_query: str | None = None


def _parse_h2_list(scrape: ScrapeResult) -> list[str]:
    if not scrape.h2_list_json:
        return []
    try:
        parsed = json.loads(scrape.h2_list_json)
        if isinstance(parsed, list):
            return [str(h) for h in parsed]
    except json.JSONDecodeError:
        pass
    return []


def _meta_needs_fix(meta: str | None) -> bool:
    if not meta or not meta.strip():
        return True
    length = len(meta.strip())
    return length < 70 or length > 160


def _build_plans(
    analysis: Analysis,
    scrape: ScrapeResult,
    probe_rows: list[LLMProbeResult],
    gsc_rows: list[GSCOpportunity],
) -> list[ProposalPlan]:
    plans: list[ProposalPlan] = []

    if scrape.images_without_alt > 0:
        plans.append(
            ProposalPlan(
                proposal_type=ProposalType.ALT_TEXT_FIX,
                title="Corregir textos alt en imágenes",
                summary=f"{scrape.images_without_alt} imágenes sin atributo alt detectadas.",
                severity=Severity.MEDIUM,
                trigger_source=TriggerSource.SCRAPE,
            )
        )

    if _meta_needs_fix(scrape.meta_description):
        plans.append(
            ProposalPlan(
                proposal_type=ProposalType.META_DESCRIPTION,
                title="Optimizar meta description",
                summary="La meta description está ausente o fuera del rango ideal (70-160 caracteres).",
                severity=Severity.HIGH,
                trigger_source=TriggerSource.SCRAPE,
            )
        )

    if not scrape.has_faq_schema:
        plans.append(
            ProposalPlan(
                proposal_type=ProposalType.FAQ_SCHEMA,
                title="Agregar FAQ schema.org",
                summary="No se detectó schema FAQPage; agregar preguntas frecuentes estructuradas.",
                severity=Severity.HIGH,
                trigger_source=TriggerSource.SCRAPE,
            )
        )

    if not scrape.has_structured_data:
        plans.append(
            ProposalPlan(
                proposal_type=ProposalType.SCHEMA_MARKUP,
                title="Agregar datos estructurados JSON-LD",
                summary="La página no tiene application/ld+json; agregar schema markup.",
                severity=Severity.MEDIUM,
                trigger_source=TriggerSource.SCRAPE,
            )
        )

    if (analysis.geo_score or 0) < 60:
        plans.append(
            ProposalPlan(
                proposal_type=ProposalType.GEO_INSIGHT,
                title="Insight GEO: por qué los LLM no citan esta página",
                summary=f"GEO Score bajo ({analysis.geo_score}/100). Revisar oportunidades de mejora.",
                severity=Severity.HIGH,
                trigger_source=TriggerSource.SCRAPE,
            )
        )

    probe_blogs = 0
    for row in probe_rows:
        if not row.needs_content:
            continue
        if probe_blogs >= MAX_PROBE_BLOGS:
            break
        plans.append(
            ProposalPlan(
                proposal_type=ProposalType.BLOG_POST,
                title=f"Blog GEO: {row.query[:60]}",
                summary="Serfinanza no fue mencionada en el LLM probe para esta query.",
                severity=Severity.HIGH,
                trigger_source=TriggerSource.LLM_PROBE,
                trigger_query=row.query,
            )
        )
        probe_blogs += 1

    if gsc_rows and scrape.word_count < 800:
        worst = max(gsc_rows, key=lambda g: g.position)
        if worst.position >= 15:
            plans.append(
                ProposalPlan(
                    proposal_type=ProposalType.BLOG_POST,
                    title=f"Blog SEO: {worst.query[:60]}",
                    summary=(
                        f"Oportunidad GSC con posición {worst.position:.1f} "
                        f"y {worst.impressions} impresiones."
                    ),
                    severity=Severity.MEDIUM,
                    trigger_source=TriggerSource.GSC,
                    trigger_query=worst.query,
                )
            )

    return plans


def _generate_content(
    plan: ProposalPlan,
    scrape: ScrapeResult,
    client: GeminiClient,
    seo_score: int | None,
    geo_score: int | None,
    learnings: list[str] | None = None,
) -> str:
    title = scrape.title or ""
    meta = scrape.meta_description or ""
    h1 = scrape.h1 or ""
    h2_list = _parse_h2_list(scrape)
    body = scrape.body_text or ""
    learnings = learnings or []

    if plan.proposal_type == ProposalType.META_DESCRIPTION:
        return client.generate(
            templates.prompt_meta_description(title, meta, h1, h2_list, body, learnings)
        )

    if plan.proposal_type == ProposalType.FAQ_SCHEMA:
        data = client.generate_json(
            templates.prompt_faq_schema(title, meta, h1, h2_list, body, learnings)
        )
        return json.dumps(data, ensure_ascii=False, indent=2)

    if plan.proposal_type == ProposalType.ALT_TEXT_FIX:
        data = client.generate_json(
            templates.prompt_alt_text_fix(
                title, meta, h1, h2_list, body, scrape.images_without_alt, learnings
            )
        )
        return json.dumps(data, ensure_ascii=False, indent=2)

    if plan.proposal_type == ProposalType.SCHEMA_MARKUP:
        data = client.generate_json(
            templates.prompt_schema_markup(title, meta, h1, h2_list, body, learnings)
        )
        return json.dumps(data, ensure_ascii=False, indent=2)

    if plan.proposal_type == ProposalType.BLOG_POST:
        return client.generate(
            templates.prompt_blog_post(
                title, meta, h1, h2_list, body, topic_query=plan.trigger_query, learnings=learnings
            )
        )

    if plan.proposal_type == ProposalType.GEO_INSIGHT:
        data = client.generate_json(
            templates.prompt_geo_insight(
                title, meta, h1, h2_list, body, seo_score=seo_score, geo_score=geo_score, learnings=learnings
            )
        )
        return json.dumps(data, ensure_ascii=False, indent=2)

    raise ValueError(f"Tipo de propuesta no soportado: {plan.proposal_type}")


def _finalize_content(raw: str, proposal_type: ProposalType) -> str:
    from app.services.content_utils import clean_gemini_output

    return clean_gemini_output(raw)


def generate_proposals(
    analysis_id: int,
    db: Session,
    client: GeminiClient | None = None,
) -> list[Proposal]:
    """
    Analiza hallazgos del scrape, probe y GSC; genera propuestas con Gemini y las guarda.
    """
    analysis = db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"No existe análisis con id {analysis_id}.")

    if analysis.status != AnalysisStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail="El análisis debe estar completado antes de generar propuestas.",
        )

    scrape = (
        db.query(ScrapeResult)
        .filter(ScrapeResult.analysis_id == analysis_id)
        .one_or_none()
    )
    if not scrape:
        raise HTTPException(
            status_code=400,
            detail="El análisis no tiene datos de scrape. Ejecuta /analyze primero.",
        )

    probe_rows = (
        db.query(LLMProbeResult)
        .filter(LLMProbeResult.analysis_id == analysis_id)
        .order_by(LLMProbeResult.created_at.desc())
        .all()
    )
    gsc_rows = db.query(GSCOpportunity).order_by(GSCOpportunity.impressions.desc()).all()

    plans = _build_plans(analysis, scrape, probe_rows, gsc_rows)
    if not plans:
        logger.info("Sin hallazgos accionables para analysis_id=%s", analysis_id)
        return []

    gemini = client or get_gemini_client()
    learnings = get_rejection_learnings(db)
    created: list[Proposal] = []
    quota_exhausted = False

    for plan in plans:
        try:
            content = _finalize_content(
                _generate_content(
                    plan, scrape, gemini, analysis.seo_score, analysis.geo_score, learnings
                ),
                plan.proposal_type,
            )
        except HTTPException as exc:
            if exc.status_code == 429:
                quota_exhausted = True
            logger.warning("Gemini falló para propuesta %s; se omite.", plan.proposal_type)
            continue

        proposal = Proposal(
            analysis_id=analysis_id,
            proposal_type=plan.proposal_type.value,
            title=plan.title,
            summary=plan.summary,
            content=content,
            severity=plan.severity.value,
            trigger_source=plan.trigger_source.value,
            trigger_query=plan.trigger_query,
            status=ProposalStatus.PENDING.value,
        )
        db.add(proposal)
        created.append(proposal)

    db.commit()
    for proposal in created:
        db.refresh(proposal)

    logger.info("Generadas %s propuestas para analysis_id=%s", len(created), analysis_id)

    if not created and quota_exhausted:
        raise HTTPException(
            status_code=429,
            detail=(
                "Cuota de Gemini agotada (free tier: ~20 solicitudes/día). "
                "Espera al reset diario o usa otra API key en GEMINI_API_KEY."
            ),
        )

    return created


def generate_proposals_for_all(
    db: Session,
    analysis_ids: list[int] | None = None,
    skip_existing: bool = True,
    client: GeminiClient | None = None,
) -> dict:
    """
    Genera propuestas para todos los análisis completed (o una lista dada).
    Omite análisis que ya tienen propuestas si skip_existing=True.
    """
    query = db.query(Analysis).filter(Analysis.status == AnalysisStatus.COMPLETED.value)
    if analysis_ids:
        query = query.filter(Analysis.id.in_(analysis_ids))

    analyses = query.order_by(Analysis.created_at.asc()).all()
    if not analyses:
        raise HTTPException(
            status_code=404,
            detail="No hay análisis completados para generar propuestas.",
        )

    results: list[dict] = []
    processed = 0
    skipped = 0
    failed = 0
    quota_exhausted = False
    total_proposals_created = 0

    for analysis in analyses:
        if skip_existing:
            has_proposals = (
                db.query(Proposal)
                .filter(Proposal.analysis_id == analysis.id)
                .count()
                > 0
            )
            if has_proposals:
                skipped += 1
                results.append(
                    {
                        "analysis_id": analysis.id,
                        "url": analysis.url,
                        "proposals_created": 0,
                        "proposals": [],
                        "skipped": True,
                        "error": None,
                    }
                )
                continue

        try:
            proposals = generate_proposals(analysis.id, db, client=client)
            processed += 1
            total_proposals_created += len(proposals)
            results.append(
                {
                    "analysis_id": analysis.id,
                    "url": analysis.url,
                    "proposals_created": len(proposals),
                    "proposals": proposals,
                    "skipped": False,
                    "error": None,
                }
            )
        except HTTPException as exc:
            failed += 1
            if exc.status_code == 429:
                quota_exhausted = True
            results.append(
                {
                    "analysis_id": analysis.id,
                    "url": analysis.url,
                    "proposals_created": 0,
                    "proposals": [],
                    "skipped": False,
                    "error": str(exc.detail),
                }
            )
        except Exception as exc:
            failed += 1
            logger.exception("recommend-all falló analysis_id=%s: %s", analysis.id, exc)
            results.append(
                {
                    "analysis_id": analysis.id,
                    "url": analysis.url,
                    "proposals_created": 0,
                    "proposals": [],
                    "skipped": False,
                    "error": "Error inesperado al generar propuestas.",
                }
            )

    logger.info(
        "recommend-all: %s análisis, %s procesados, %s omitidos, %s fallidos, %s propuestas",
        len(analyses),
        processed,
        skipped,
        failed,
        total_proposals_created,
    )

    if processed > 0 and total_proposals_created == 0 and quota_exhausted:
        raise HTTPException(
            status_code=429,
            detail=(
                "Cuota de Gemini agotada. Ninguna propuesta pudo generarse. "
                "Espera al reset diario o cambia GEMINI_API_KEY en .env y reinicia uvicorn."
            ),
        )

    if processed == 0 and skipped > 0 and skip_existing:
        logger.info("recommend-all: todos los análisis ya tenían propuestas (skip_existing=true)")

    return {
        "total_analyses": len(analyses),
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "total_proposals_created": total_proposals_created,
        "results": results,
    }
