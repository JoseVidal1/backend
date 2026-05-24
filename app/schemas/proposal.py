from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.enums import ProposalStatus, ProposalType, Severity, TriggerSource
from app.schemas.common import PaginatedResponse


class RecommendRequest(BaseModel):
    analysis_id: int = Field(..., gt=0)


class ProposalSummary(BaseModel):
    id: int
    analysis_id: Optional[int] = None
    proposal_type: ProposalType
    title: str
    summary: Optional[str] = None
    severity: Severity
    status: ProposalStatus
    trigger_source: TriggerSource
    trigger_query: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProposalFeedbackSchema(BaseModel):
    id: int
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImpactMeasurementSchema(BaseModel):
    id: int
    llm_mentioned_after: bool
    similarity_score_after: float
    google_position_after: float
    measured_at: datetime

    model_config = {"from_attributes": True}


class ProposalDetail(BaseModel):
    id: int
    analysis_id: Optional[int] = None
    proposal_type: ProposalType
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    severity: Severity
    trigger_source: TriggerSource
    trigger_query: Optional[str] = None
    status: ProposalStatus
    wp_published_url: Optional[str] = None
    wp_published_id: Optional[int] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    feedbacks: list[ProposalFeedbackSchema] = Field(default_factory=list)
    impact_measurements: list[ImpactMeasurementSchema] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RecommendResponse(BaseModel):
    analysis_id: int
    proposals_created: int
    proposals: list[ProposalSummary]


class RecommendAllRequest(BaseModel):
    """Genera propuestas para múltiples análisis en una sola llamada."""

    analysis_ids: Optional[list[int]] = Field(
        default=None,
        description="IDs específicos. Si no se envían, procesa todos los análisis completed.",
    )
    skip_existing: bool = Field(
        default=True,
        description="Si true, omite análisis que ya tienen propuestas generadas.",
    )


class RecommendAllResultItem(BaseModel):
    analysis_id: int
    url: str
    proposals_created: int
    proposals: list[ProposalSummary] = Field(default_factory=list)
    skipped: bool = False
    error: Optional[str] = None


class RecommendAllResponse(BaseModel):
    total_analyses: int
    processed: int
    skipped: int
    failed: int
    total_proposals_created: int
    results: list[RecommendAllResultItem]


class ProposalListFilters(BaseModel):
    """Query params para GET /proposals."""

    status: Optional[ProposalStatus] = None
    proposal_type: Optional[ProposalType] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("El motivo de rechazo no puede estar vacío.")
        return cleaned


class ProposalApproveResponse(BaseModel):
    id: int
    status: ProposalStatus
    wp_published_url: Optional[str] = None
    wp_published_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None


class ProposalRejectResponse(BaseModel):
    id: int
    status: ProposalStatus
    feedback_id: int
    reviewed_at: Optional[datetime] = None


class MeasureImpactResponse(BaseModel):
    proposal_id: int
    measurement: ImpactMeasurementSchema
    improvement_summary: str


class ProposalPreviewResponse(BaseModel):
    """Previsualización para el editor antes de aprobar o rechazar."""

    id: int
    analysis_id: Optional[int] = None
    analysis_url: Optional[str] = None
    proposal_type: ProposalType
    title: str
    summary: Optional[str] = None
    severity: Severity
    status: ProposalStatus
    trigger_source: TriggerSource
    trigger_query: Optional[str] = None
    content_raw: str
    content_html: str
    publish_action: str = Field(
        description="create_post | patch_meta | append_to_post | update_alt"
    )
    publish_action_label: str
    target_post_id: Optional[int] = None
    target_media_id: Optional[int] = None
    wordpress_url: Optional[str] = None
    can_review: bool = Field(description="True si status=pending y se puede aprobar/rechazar")
    pending_count: int = Field(description="Total de propuestas pendientes en cola")
    approve_url: str = Field(description="Ruta relativa para aprobar: POST /proposals/{id}/approve")
    reject_url: str = Field(description="Ruta relativa para rechazar: POST /proposals/{id}/reject")


ProposalListResponse = PaginatedResponse[ProposalSummary]
