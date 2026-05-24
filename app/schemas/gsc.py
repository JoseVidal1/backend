from datetime import datetime

from pydantic import BaseModel


class GSCOpportunitySchema(BaseModel):
    id: int
    query: str
    impressions: int
    position: float
    ctr: float
    imported_at: datetime

    model_config = {"from_attributes": True}


class GSCOpportunityListResponse(BaseModel):
    items: list[GSCOpportunitySchema]
    total: int
