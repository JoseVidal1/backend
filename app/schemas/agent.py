from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator

from app.schemas.analysis import ScrapeSummary
from app.schemas.proposal import ProposalSummary


class RunFullCycleRequest(BaseModel):
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
