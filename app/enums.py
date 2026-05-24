from enum import Enum


class AnalysisStatus(str, Enum):
    """Estado de un análisis de URL."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ProposalType(str, Enum):
    """Tipo de propuesta generada por el recommender."""

    BLOG_POST = "BLOG_POST"
    META_DESCRIPTION = "META_DESCRIPTION"
    FAQ_SCHEMA = "FAQ_SCHEMA"
    ALT_TEXT_FIX = "ALT_TEXT_FIX"
    SCHEMA_MARKUP = "SCHEMA_MARKUP"
    GEO_INSIGHT = "GEO_INSIGHT"


class ProposalStatus(str, Enum):
    """Estado del flujo de aprobación (verbo EDITAR)."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Severity(str, Enum):
    """Prioridad de la propuesta para el dashboard."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TriggerSource(str, Enum):
    """Qué hallazgo disparó la propuesta."""

    SCRAPE = "scrape"
    LLM_PROBE = "llm_probe"
    GSC = "gsc"
