#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from antibot_image_solver.models import AntibotChallenge, OptionImage
from antibot_image_solver.solver import solve_challenge
from label_claimcoin_antibot import best_text, load_capture


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_path")
    args = ap.parse_args()
    capture = load_capture(Path(args.capture_path))
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
    payload = {
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
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
