import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.llm_probe import LLMProbeResult
from app.schemas.common import PaginatedResponse


class ProbeRunRequest(BaseModel):
    """Body opcional para POST /probe/run."""

    queries: Optional[list[str]] = Field(
        default=None,
        description="Queries personalizadas. Si no se envían, usa las queries financieras por defecto.",
    )
    analysis_id: Optional[int] = Field(
        default=None,
        description="ID del análisis al que vincular los resultados del probe.",
    )


class ProbeResultItem(BaseModel):
    id: int
    analysis_id: Optional[int] = None
    query: str
    llm_response_excerpt: Optional[str] = None
    serfinanza_mentioned: bool = False
    competitors_mentioned: list[str] = Field(default_factory=list)
    similarity_score: float = 0.0
    needs_content: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def parse_from_orm(cls, data):
        if isinstance(data, LLMProbeResult):
            competitors: list[str] = []
            if data.competitors_mentioned_json:
                try:
                    parsed = json.loads(data.competitors_mentioned_json)
                    if isinstance(parsed, list):
                        competitors = [str(c) for c in parsed]
                except json.JSONDecodeError:
                    competitors = []
            return {
                "id": data.id,
                "analysis_id": data.analysis_id,
                "query": data.query,
                "llm_response_excerpt": data.llm_response_excerpt,
                "serfinanza_mentioned": data.serfinanza_mentioned,
                "competitors_mentioned": competitors,
                "similarity_score": data.similarity_score,
                "needs_content": data.needs_content,
                "created_at": data.created_at,
            }
        return data


class ProbeRunResponse(BaseModel):
    results: list[ProbeResultItem]
    total: int


ProbeResultListResponse = PaginatedResponse[ProbeResultItem]
