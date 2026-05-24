from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.schemas.analysis import BulkAnalyzeItem, ScrapeSummary
from app.schemas.proposal import ProposalSummary, RecommendAllResultItem


class RunFullCycleRequest(BaseModel):
    """Una URL: audit + probe + propuestas."""

    url: HttpUrl

    @field_validator("url")
    @classmethod
    def url_must_have_scheme(cls, v):
        if str(v).startswith(("http://", "https://")):
            return v
        raise ValueError("La URL debe comenzar con http:// o https://")


class RunFullCycleResponse(BaseModel):
    analysis_id: int
    url: str
    seo_score: Optional[int] = None
    geo_score: Optional[int] = None
    probe_results_count: int
    proposals_count: int
    scrape_summary: Optional[ScrapeSummary] = None
    scrape_warning: Optional[str] = None
    proposals: list[ProposalSummary] = []


class RunSiteCycleRequest(BaseModel):
    """Sitio WordPress completo: auditar todas las páginas + generar propuestas."""

    wordpress_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL base del sitio WP. Default: WORDPRESS_URL del .env.",
    )
    include_posts: bool = Field(default=True, description="Incluir entradas de blog además de páginas.")
    status: str = Field(default="publish", description="Estado WP: publish, draft, etc.")
    skip_existing: bool = Field(
        default=True,
        description="Omite análisis que ya tienen propuestas generadas.",
    )


class RunSiteCycleResponse(BaseModel):
    source: str
    total_found: int
    analyzed: int
    audit_failed: int
    audit_results: list[BulkAnalyzeItem]
    processed: int
    skipped: int
    recommend_failed: int
    total_proposals_created: int
    recommend_results: list[RecommendAllResultItem]
