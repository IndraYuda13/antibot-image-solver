from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class OptionImage:
    id: str
    image_base64: str
    text_candidates: list[str] = field(default_factory=list)
    canonical_forms: set[str] = field(default_factory=set)


@dataclass
class AntibotChallenge:
    instruction_image_base64: str
    options: list[OptionImage] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    domain_hint: Optional[str] = None
    request_id: Optional[str] = None


@dataclass
class SolveDebug:
    instruction_ocr: list[str] = field(default_factory=list)
    instruction_token_sets: list[list[str]] = field(default_factory=list)
    option_ocr: dict[str, list[str]] = field(default_factory=dict)
    option_forms: dict[str, list[str]] = field(default_factory=dict)
    best_score: int = 0
    second_best_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SolveResult:
    success: bool
    status: str
    ordered_ids: list[str] = field(default_factory=list)
    ordered_candidates: list[str] = field(default_factory=list)
    indexes_1based: list[int] = field(default_factory=list)
    confidence: float = 0.0
    family: Optional[str] = None
    tokens_detected: list[str] = field(default_factory=list)
    debug: Optional[SolveDebug] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_debug: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "status": self.status,
            "solution": {
                "ordered_ids": self.ordered_ids,
                "ordered_candidates": self.ordered_candidates,
                "indexes_1based": self.indexes_1based,
            },
            "confidence": self.confidence,
            "meta": {
                "family": self.family,
                "tokens_detected": self.tokens_detected,
                **self.meta,
            },
        }
        if not self.success:
            payload["error"] = {
                "code": self.error_code or "SOLVER_ERROR",
                "message": self.error_message or "solver failed",
            }
        if include_debug and self.debug is not None:
            payload["debug"] = self.debug.to_dict()
        return payload
