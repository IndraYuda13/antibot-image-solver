from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from antibot_image_solver.models import AntibotChallenge, SolveResult

CaptureVerdict = Literal["success", "reject_antibot", "reject_captcha_or_session", "uncertain"]
ALLOWED_VERDICTS: set[str] = {
    "success",
    "reject_antibot",
    "reject_captcha_or_session",
    "uncertain",
}


@dataclass
class CaptureRequest:
    output_dir: str
    verdict: CaptureVerdict
    source: str = "unknown"
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    challenge_id: str | None = None


class CaptureError(RuntimeError):
    pass


class CaptureValidationError(CaptureError):
    pass


class CaptureWriteError(CaptureError):
    pass


def validate_verdict(verdict: str) -> str:
    verdict_normalized = verdict.strip().lower()
    if verdict_normalized not in ALLOWED_VERDICTS:
        allowed = ", ".join(sorted(ALLOWED_VERDICTS))
        raise CaptureValidationError(f"invalid verdict {verdict!r}; expected one of: {allowed}")
    return verdict_normalized


def persist_capture(
    challenge: AntibotChallenge,
    result: SolveResult,
    capture: CaptureRequest,
    *,
    include_debug: bool = True,
) -> dict[str, Any]:
    verdict = validate_verdict(capture.verdict)
    root = Path(capture.output_dir).expanduser()
    timestamp = datetime.now(timezone.utc)
    challenge_id = _build_challenge_id(challenge, capture, timestamp)
    record_dir = root / challenge_id
    try:
        record_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise CaptureWriteError(f"capture directory already exists: {record_dir}") from exc

    payload = {
        "challenge_id": challenge_id,
        "captured_at": timestamp.isoformat(),
        "verdict": verdict,
        "source": capture.source,
        "notes": capture.notes,
        "tags": capture.tags,
        "challenge": _challenge_payload(challenge),
        "result": result.to_dict(include_debug=include_debug),
    }
    try:
        (record_dir / "record.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        summary = _summary_payload(payload)
        (root / "index.jsonl").parent.mkdir(parents=True, exist_ok=True)
        with (root / "index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise CaptureWriteError(f"failed to write capture record to {record_dir}") from exc

    return {"challenge_id": challenge_id, "record_path": str(record_dir / 'record.json'), "index_path": str(root / 'index.jsonl')}


def _build_challenge_id(challenge: AntibotChallenge, capture: CaptureRequest, timestamp: datetime) -> str:
    if capture.challenge_id:
        return capture.challenge_id
    if challenge.request_id:
        return challenge.request_id
    return timestamp.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]


def _challenge_payload(challenge: AntibotChallenge) -> dict[str, Any]:
    return {
        "request_id": challenge.request_id,
        "domain_hint": challenge.domain_hint,
        "instruction_image_base64": challenge.instruction_image_base64,
        "candidates": list(challenge.candidates),
        "options": [
            {
                "id": option.id,
                "image_base64": option.image_base64,
                "text_candidates": list(option.text_candidates),
                "canonical_forms": sorted(option.canonical_forms),
            }
            for option in challenge.options
        ],
    }


def _summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload["result"]
    meta = result.get("meta") or {}
    solution = result.get("solution") or {}
    return {
        "challenge_id": payload["challenge_id"],
        "captured_at": payload["captured_at"],
        "verdict": payload["verdict"],
        "source": payload["source"],
        "domain_hint": payload["challenge"].get("domain_hint"),
        "success": result.get("success"),
        "status": result.get("status"),
        "confidence": result.get("confidence"),
        "family": meta.get("family"),
        "tokens_detected": meta.get("tokens_detected") or [],
        "ordered_ids": solution.get("ordered_ids") or [],
        "ordered_candidates": solution.get("ordered_candidates") or [],
        "record_path": f"{payload['challenge_id']}/record.json",
    }
