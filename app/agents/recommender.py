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
) -> str:
    title = scrape.title or ""
    meta = scrape.meta_description or ""
    h1 = scrape.h1 or ""
    h2_list = _parse_h2_list(scrape)
    body = scrape.body_text or ""

    if plan.proposal_type == ProposalType.META_DESCRIPTION:
        return client.generate(
            templates.prompt_meta_description(title, meta, h1, h2_list, body)
        )

    if plan.proposal_type == ProposalType.FAQ_SCHEMA:
        data = client.generate_json(
            templates.prompt_faq_schema(title, meta, h1, h2_list, body)
        )
        return json.dumps(data, ensure_ascii=False, indent=2)

    if plan.proposal_type == ProposalType.ALT_TEXT_FIX:
        data = client.generate_json(
            templates.prompt_alt_text_fix(
                title, meta, h1, h2_list, body, scrape.images_without_alt
            )
        )
        return json.dumps(data, ensure_ascii=False, indent=2)

    if plan.proposal_type == ProposalType.SCHEMA_MARKUP:
        data = client.generate_json(
            templates.prompt_schema_markup(title, meta, h1, h2_list, body)
        )
        return json.dumps(data, ensure_ascii=False, indent=2)

    if plan.proposal_type == ProposalType.BLOG_POST:
        return client.generate(
            templates.prompt_blog_post(
                title, meta, h1, h2_list, body, topic_query=plan.trigger_query
            )
        )

    if plan.proposal_type == ProposalType.GEO_INSIGHT:
        data = client.generate_json(
            templates.prompt_geo_insight(
                title, meta, h1, h2_list, body, seo_score=seo_score, geo_score=geo_score
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
    created: list[Proposal] = []

    for plan in plans:
        try:
            content = _finalize_content(
                _generate_content(
                    plan, scrape, gemini, analysis.seo_score, analysis.geo_score
                ),
                plan.proposal_type,
            )
        except HTTPException:
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
    return created
