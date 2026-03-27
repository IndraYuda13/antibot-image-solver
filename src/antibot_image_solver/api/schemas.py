from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class OptionImagePayload(BaseModel):
    id: str = Field(..., description="Stable option id or rel attribute")
    image_base64: str = Field(..., description="Base64 encoded option image")


class SolveRequest(BaseModel):
    instruction_image_base64: str = Field(..., description="Base64 encoded instruction image")
    options: list[OptionImagePayload] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)
    domain_hint: Optional[str] = None
    request_id: Optional[str] = None
    debug: bool = False

    @model_validator(mode="after")
    def validate_payload(self) -> "SolveRequest":
        if not self.options and not self.candidates:
            raise ValueError("either options or candidates must be provided")
        return self


class AnalyzeRequest(BaseModel):
    instruction_image_base64: str


class ErrorPayload(BaseModel):
    code: str
    message: str


class SolveResponse(BaseModel):
    success: bool
    status: str
    request_id: Optional[str] = None
    solution: dict[str, Any] | None = None
    confidence: float | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    error: ErrorPayload | None = None
    debug: dict[str, Any] | None = None
