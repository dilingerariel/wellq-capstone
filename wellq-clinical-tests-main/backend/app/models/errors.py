"""The documented envelope matches the existing detail-object wire contract."""
from typing import Any
from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: str
    message: str | None = None
    errors: list[dict[str, Any]] | None = None
    reason: str | None = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail
