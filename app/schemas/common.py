from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Respuesta paginada genérica para listados."""

    items: list[T]
    total: int
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
