from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from antibot_image_solver.models import SolveResult

SCHEMA_VERSION = "antibot-image-solver.ranker-shadow.v1"


def _base_payload(result: SolveResult, *, request_id: str | None) -> dict[str, Any]:
    production_order = list(result.ordered_ids)
    debug = result.debug.to_dict() if result.debug is not None else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "shadow_no_submit",
        "no_submit": True,
        "request_id": request_id,
        "production_order": production_order,
        "shadow_order": production_order,
        "would_override": False,
        "solver_confidence": result.confidence,
        "solver_status": result.status,
        "solver_success": result.success,
        "family": result.family,
        "debug": debug,
    }


def _provider_decision(provider_command: str, payload: dict[str, Any]) -> dict[str, Any]:
    proc = subprocess.run(
        shlex.split(provider_command),
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"provider exited {proc.returncode}")
    return json.loads(proc.stdout)


def build_shadow_decision(
    result: SolveResult,
    *,
    request_id: str | None = None,
    provider_command: str | None = None,
) -> dict[str, Any]:
    payload = _base_payload(result, request_id=request_id)
    if not provider_command:
        payload.update(
            {
                "status": "logged_production_only",
                "note": "Shadow hook preserves production order. No external AI ranker provider was configured.",
            }
        )
        return payload

    try:
        decision = _provider_decision(provider_command, payload)
        payload.update(
            {
                "status": "provider_decision_logged",
                "shadow_order": [str(item) for item in decision.get("shadow_order", payload["production_order"])],
                "would_override": bool(decision.get("would_override", False)),
                "ai_confidence": float(decision.get("ai_confidence", 0.0)),
                "override_probability": float(decision.get("override_probability", 0.0)),
                "provider": decision.get("provider"),
            }
        )
    except Exception as exc:  # provider must never break production solving
        payload.update(
            {
                "status": "provider_error_fallback",
                "provider_error": str(exc),
                "shadow_order": payload["production_order"],
                "would_override": False,
            }
        )
    return payload


def append_shadow_decision(
    path: str | Path,
    result: SolveResult,
    *,
    request_id: str | None = None,
    provider_command: str | None = None,
) -> dict[str, Any]:
    payload = build_shadow_decision(result, request_id=request_id, provider_command=provider_command)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload
