#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from antibot_image_solver.matcher import MatchEntry, solve_from_hypotheses
from antibot_image_solver.models import AntibotChallenge, OptionImage
from antibot_image_solver.normalize import canonical_forms, guess_family
from antibot_image_solver.solver import solve_challenge
from label_claimcoin_antibot import best_text, load_capture


def _payload_from_debug(capture: dict) -> dict:
    challenge = capture.get("challenge") or {}
    items = challenge.get("items") or []
    solver = capture.get("solver") or {}
    debug = solver.get("debug") or {}
    instruction_ocr = debug.get("instruction_ocr") or []
    option_ocr = {str(k): [str(x) for x in (v or [])] for k, v in (debug.get("option_ocr") or {}).items()}
    entries = []
    for item in items:
        oid = str(item.get("id"))
        candidates = option_ocr.get(oid, [])
        forms = set()
        for candidate in candidates:
            forms |= canonical_forms(candidate)
        entries.append(MatchEntry(id=oid, display=best_text(candidates) or oid, candidates=candidates, forms=forms))
    try:
        outcome = solve_from_hypotheses(instruction_ocr, entries)
        return {
            "success": True,
            "status": "solved",
            "question_text": best_text(instruction_ocr),
            "question_tokens": outcome.tokens_detected,
            "options_text": {str(k): best_text(v) for k, v in option_ocr.items()},
            "submitted_answer_order": [str(x) for x in outcome.ordered_ids],
            "confidence": outcome.confidence,
            "tesseract_question_ocr": instruction_ocr,
            "tesseract_option_ocr": option_ocr,
            "error_code": None,
            "error_message": None,
            "meta": {"mode": "stored_debug", "family": guess_family(outcome.tokens_detected)},
        }
    except Exception as exc:
        return {
            "success": False,
            "status": "error",
            "question_text": best_text(instruction_ocr),
            "question_tokens": [],
            "options_text": {str(k): best_text(v) for k, v in option_ocr.items()},
            "submitted_answer_order": [],
            "confidence": 0.0,
            "tesseract_question_ocr": instruction_ocr,
            "tesseract_option_ocr": option_ocr,
            "error_code": type(exc).__name__,
            "error_message": str(exc),
            "meta": {"mode": "stored_debug"},
        }


def _payload_from_current_ocr(capture: dict) -> dict:
    challenge = capture.get("challenge") or {}
    items = challenge.get("items") or []
    solver_input = AntibotChallenge(
        instruction_image_base64=str(challenge.get("main_image") or ""),
        options=[OptionImage(id=str(item.get("id")), image_base64=str(item.get("image") or "")) for item in items],
        domain_hint=str(challenge.get("domain_hint") or "claimcoin"),
        request_id=str(capture.get("attempt_id") or ""),
    )
    result = solve_challenge(solver_input, debug=True)
    debug = result.debug.to_dict() if result.debug else {}
    option_ocr = debug.get("option_ocr") or {}
    question_ocr = debug.get("instruction_ocr") or []
    return {
        "success": result.success,
        "status": result.status,
        "question_text": best_text(question_ocr),
        "question_tokens": list(result.tokens_detected or []),
        "options_text": {str(k): best_text(v) for k, v in option_ocr.items()},
        "submitted_answer_order": [str(x) for x in (result.ordered_ids or [])],
        "confidence": result.confidence,
        "tesseract_question_ocr": question_ocr,
        "tesseract_option_ocr": option_ocr,
        "error_code": result.error_code,
        "error_message": result.error_message,
        "meta": result.meta,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_path")
    ap.add_argument("--mode", choices=["stored-debug", "current-ocr"], default="current-ocr")
    args = ap.parse_args()
    capture = load_capture(Path(args.capture_path))
    if args.mode == "stored-debug":
        payload = _payload_from_debug(capture)
    else:
        payload = _payload_from_current_ocr(capture)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
