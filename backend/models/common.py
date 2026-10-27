from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    """Standard success response envelope per decisions.md Section 4 and rules.md."""
    data: T
    message: str = "Success"


class PaginatedEnvelope(BaseModel, Generic[T]):
    """Standard paginated list response envelope per decisions.md Section 4 and rules.md."""
    data: list[T]
    total: int
    page: int = 1
    page_size: int = 20


class ErrorEnvelope(BaseModel):
    """Standard error response envelope per decisions.md Section 4 and rules.md."""
    detail: str
    error_code: str = "ERROR"
