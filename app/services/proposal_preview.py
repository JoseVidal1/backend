"""Renderiza previsualización de propuestas como se verían al publicar en WordPress."""

from app.config import settings
from app.enums import ProposalType
from app.services.content_utils import clean_gemini_output
from app.services.wordpress_adapter import WordPressRestAdapter, _target_post_id

_PUBLISH_PLAN: dict[ProposalType, dict] = {
    ProposalType.BLOG_POST: {
        "action": "create_post",
        "label": "Crear nueva entrada en WordPress",
    },
    ProposalType.META_DESCRIPTION: {
        "action": "patch_meta",
        "label": "Actualizar meta description del post existente",
    },
    ProposalType.FAQ_SCHEMA: {
        "action": "append_to_post",
        "label": "Agregar sección FAQ al final del post existente",
    },
    ProposalType.SCHEMA_MARKUP: {
        "action": "append_to_post",
        "label": "Agregar JSON-LD schema al post existente",
    },
    ProposalType.ALT_TEXT_FIX: {
        "action": "update_alt",
        "label": "Actualizar texto alt de imagen en medios",
    },
    ProposalType.GEO_INSIGHT: {
        "action": "append_to_post",
        "label": "Agregar bloque Insight GEO al post existente",
    },
}


def _render_html(proposal_type: ProposalType, content: str) -> str:
    body = clean_gemini_output(content or "")

    if proposal_type == ProposalType.META_DESCRIPTION:
        return (
            '<div style="font-family: Segoe UI, Arial, sans-serif; padding: 16px; '
            'background: #f0f6fc; border-left: 4px solid #0066cc; margin: 8px 0;">'
            '<p style="margin: 0 0 8px; font-size: 12px; color: #666; '
            'text-transform: uppercase; letter-spacing: 0.5px;">Meta description</p>'
            f'<p style="margin: 0; color: #003366; font-size: 15px; line-height: 1.5;">{body}</p>'
            f'<p style="margin: 8px 0 0; font-size: 12px; color: #888;">'
            f"{len(body)} caracteres</p></div>"
        )

    if proposal_type == ProposalType.SCHEMA_MARKUP:
        return WordPressRestAdapter._schema_to_script(body)

    if body.lstrip().startswith(("{", "[")):
        return WordPressRestAdapter._json_to_html(body, proposal_type)

    return WordPressRestAdapter._markdown_to_html(body)


def build_proposal_preview(
    proposal_type: str,
    title: str,
    content: str | None,
) -> dict:
    """
    Genera HTML de previsualización y metadatos de publicación
    para el editor de revisión (sin tocar WordPress).
    """
    ptype = ProposalType(proposal_type)
    plan = _PUBLISH_PLAN[ptype]
    raw = clean_gemini_output(content or "")
    html = _render_html(ptype, raw)

    target_post_id = _target_post_id() if plan["action"] in ("patch_meta", "append_to_post") else None
    target_media_id = (
        settings.WORDPRESS_DEFAULT_MEDIA_ID or 1
        if plan["action"] == "update_alt"
        else None
    )

    return {
        "content_raw": raw,
        "content_html": html,
        "publish_action": plan["action"],
        "publish_action_label": plan["label"],
        "preview_title": title,
        "target_post_id": target_post_id,
        "target_media_id": target_media_id,
        "wordpress_url": settings.WORDPRESS_URL,
    }
