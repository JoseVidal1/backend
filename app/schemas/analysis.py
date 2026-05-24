import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.enums import AnalysisStatus
from app.models.scrape_result import ScrapeResult
from app.schemas.common import PaginatedResponse
from app.schemas.probe import ProbeResultItem
from app.schemas.proposal import ProposalSummary
from app.services.scraper import detect_scrape_warning


class AnalyzeRequest(BaseModel):
    url: HttpUrl

    @field_validator("url")
    @classmethod
    def url_must_have_scheme(cls, v):
        if str(v).startswith(("http://", "https://")):
            return v
        raise ValueError("La URL debe comenzar con http:// o https://")


class ScrapeSummary(BaseModel):
    """Resumen ligero del scrape para respuestas de /analyze."""

    title: Optional[str] = None
    meta_description: Optional[str] = None
    h1: Optional[str] = None
    word_count: int = 0
    has_faq_schema: bool = False
    has_structured_data: bool = False
    internal_links_count: int = 0
    images_without_alt: int = 0
    scrape_warning: Optional[str] = None


class ScrapeResultDetail(BaseModel):
    """Detalle completo del scrape para GET /analyses/{id}."""

    title: Optional[str] = None
    meta_description: Optional[str] = None
    h1: Optional[str] = None
    h2_list: list[str] = []
    body_text: Optional[str] = None
    word_count: int = 0
    has_faq_schema: bool = False
    has_structured_data: bool = False
    images_without_alt: int = 0
    internal_links_count: int = 0
    scrape_warning: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def parse_from_orm(cls, data):
        if isinstance(data, ScrapeResult):
            h2_list: list[str] = []
            if data.h2_list_json:
                try:
                    parsed = json.loads(data.h2_list_json)
                    if isinstance(parsed, list):
                        h2_list = [str(h) for h in parsed]
                except json.JSONDecodeError:
                    h2_list = []
            return {
                "title": data.title,
                "meta_description": data.meta_description,
                "h1": data.h1,
                "h2_list": h2_list,
                "body_text": data.body_text,
                "word_count": data.word_count or 0,
                "has_faq_schema": bool(data.has_faq_schema),
                "has_structured_data": bool(data.has_structured_data),
                "images_without_alt": data.images_without_alt or 0,
                "internal_links_count": data.internal_links_count or 0,
                "scrape_warning": data.scrape_warning
                or detect_scrape_warning(data.title, data.meta_description, data.body_text),
                "created_at": data.created_at,
            }
        return data


class AnalyzeResponse(BaseModel):
    analysis_id: int
    url: str
    seo_score: Optional[int] = None
    geo_score: Optional[int] = None
    status: AnalysisStatus
    scrape_summary: Optional[ScrapeSummary] = None
    scrape_warning: Optional[str] = None


class AnalyzeWordPressPagesRequest(BaseModel):
    """Audita todas las páginas del sitio WordPress vía REST API."""

    wordpress_url: Optional[HttpUrl] = Field(
        default=None,
        description=(
            "URL base del sitio WordPress (ej: https://tu-sitio.railway.app). "
            "También acepta el endpoint REST completo (/wp-json/wp/v2/pages)."
        ),
    )
    include_posts: bool = Field(
        default=False,
        description="Si true, también analiza entradas (posts) además de páginas.",
    )
    status: str = Field(
        default="publish",
        description="Estado WP a incluir: publish, draft, etc.",
    )


class BulkAnalyzeItem(BaseModel):
    analysis_id: Optional[int] = None
    url: str
    wp_id: int
    wp_title: str
    content_type: str
    seo_score: Optional[int] = None
    geo_score: Optional[int] = None
    status: AnalysisStatus
    scrape_warning: Optional[str] = None
    error: Optional[str] = None


class AnalyzeWordPressPagesResponse(BaseModel):
    source: str
    total_found: int
    analyzed: int
    failed: int
    results: list[BulkAnalyzeItem]


class AnalysisSummary(BaseModel):
    id: int
    url: str
    seo_score: Optional[int] = None
    geo_score: Optional[int] = None
    status: AnalysisStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisListFilters(BaseModel):
    """Query params para GET /analyses."""

    status: Optional[AnalysisStatus] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class AnalysisDetail(BaseModel):
    id: int
    url: str
    seo_score: Optional[int] = None
    geo_score: Optional[int] = None
    status: AnalysisStatus
    created_at: datetime
    scrape_warning: Optional[str] = None
    scrape_result: Optional[ScrapeResultDetail] = None
    probe_results: list[ProbeResultItem] = []
    proposals: list[ProposalSummary] = []


AnalysisListResponse = PaginatedResponse[AnalysisSummary]
