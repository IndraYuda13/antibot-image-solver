from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from antibot_image_solver.models import SolveResult

SCHEMA_VERSION = "antibot-image-solver.ranker-shadow.v1"


def build_shadow_decision(result: SolveResult, *, request_id: str | None = None) -> dict[str, Any]:
    production_order = list(result.ordered_ids)
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "shadow_no_submit",
        "no_submit": True,
        "request_id": request_id,
        "status": "logged_production_only",
        "production_order": production_order,
        "shadow_order": production_order,
        "would_override": False,
        "solver_confidence": result.confidence,
        "solver_status": result.status,
        "solver_success": result.success,
        "family": result.family,
        "note": "Shadow hook preserves production order. AI ranker decision is not applied in this adapter version.",
    }


def append_shadow_decision(path: str | Path, result: SolveResult, *, request_id: str | None = None) -> dict[str, Any]:
    payload = build_shadow_decision(result, request_id=request_id)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload
