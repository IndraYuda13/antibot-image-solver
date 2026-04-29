#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from antibot_image_solver.normalize import normalize_letters  # noqa: E402

DEFAULT_CLAIMCOIN_ROOT = Path("/root/.openclaw/workspace/projects/claimcoin-autoclaim")
DEFAULT_LABEL_ROOT = ROOT / "state" / "antibot-labeling"


def load_capture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_image(b64: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(b64))


def best_text(candidates: list[str] | None) -> str:
    for item in candidates or []:
        cleaned = str(item).replace("\n", " ").strip()
        if cleaned and cleaned.lower() not in {"ee", "os", "be"}:
            return cleaned
    return ""


def split_tokens(text: str, expected_count: int | None = None) -> list[str]:
    parts = [part.strip() for part in text.replace("\n", " ").split(",") if part.strip()]
    if expected_count and len(parts) != expected_count:
        spaced = [part.strip() for part in text.replace("\n", " ").split() if part.strip()]
        if len(spaced) == expected_count:
            return spaced
    return parts


def normalize_option_text(text: str) -> str:
    return normalize_letters(text).strip(", ") or text.strip().lower()


def auto_order(question_text: str, options_text: dict[str, str], option_count: int) -> list[str]:
    tokens = split_tokens(question_text, option_count)
    if len(tokens) != option_count:
        return []
    remaining = dict(options_text)
    order: list[str] = []
    for token in tokens:
        target = normalize_option_text(token)
        match_id = None
        for option_id, option_text in remaining.items():
            if normalize_option_text(option_text) == target:
                match_id = option_id
                break
        if match_id is None:
            return []
        order.append(match_id)
        remaining.pop(match_id, None)
    return order


def case_id(attempt_id: int) -> str:
    return f"claimcoin_{attempt_id:06d}"


def build_queue_case(attempt_id: int, verdict: str, capture_rel: str, claimcoin_root: Path, label_root: Path) -> dict[str, Any]:
    capture_path = claimcoin_root / capture_rel
    capture = load_capture(capture_path)
    cid = case_id(attempt_id)
    image_dir = label_root / "images" / cid
    challenge = capture.get("challenge") or {}
    solver = capture.get("solver") or {}
    debug = solver.get("debug") or {}
    items = challenge.get("items") or []

    question_rel = f"images/{cid}/question.png"
    write_image(challenge.get("main_image") or "", label_root / question_rel)
    options = []
    for item in items:
        option_id = str(item.get("id"))
        option_rel = f"images/{cid}/option_{option_id}.png"
        write_image(str(item.get("image") or ""), label_root / option_rel)
        options.append({"id": option_id, "image": option_rel})

    current_question = best_text(debug.get("instruction_ocr"))
    current_options = {str(k): best_text(v) for k, v in (debug.get("option_ocr") or {}).items()}
    submitted_order = solver.get("ordered_ids") or str(solver.get("antibotlinks") or "").split()
    option_count = len(options)
    return {
        "case_id": cid,
        "attempt_id": attempt_id,
        "status": "queued",
        "priority": "rejected" if verdict == "server_reject_antibot" else "accepted",
        "verdict": verdict,
        "source_capture_path": capture_rel,
        "option_count": option_count,
        "images": {"question": question_rel, "options": options},
        "current_solver": {
            "question_text": current_question,
            "question_tokens": split_tokens(current_question, option_count),
            "options_text": current_options,
            "submitted_answer_order": [str(item) for item in submitted_order],
            "tesseract_question_ocr": debug.get("instruction_ocr") or [],
            "tesseract_option_ocr": debug.get("option_ocr") or {},
            "confidence": solver.get("confidence"),
            "verdict": verdict,
        },
        "solver_review": {
            "question_read_correct": None,
            "option_reads_correct": {opt["id"]: None for opt in options},
            "submitted_order_correct": None,
        },
        "manual_label": {
            "question_text": "",
            "question_tokens": [],
            "options_text": {opt["id"]: "" for opt in options},
            "correct_answer_order": [],
            "notes": "",
        },
    }


def export_cases(args: argparse.Namespace) -> None:
    claimcoin_root = Path(args.claimcoin_root)
    label_root = Path(args.label_root)
    for sub in ["queue", "labeled", "skipped", "images"]:
        (label_root / sub).mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(claimcoin_root / "state" / "claimcoin.sqlite3")
    if args.priority == "rejected":
        where = "verdict='server_reject_antibot'"
    elif args.priority == "accepted":
        where = "verdict='accepted_success'"
    else:
        where = "1=1"
    rows = list(con.execute(
        f"select id,verdict,capture_path from antibot_attempts where {where} order by id desc limit ?",
        (args.limit,),
    ))
    rows.reverse()
    exported = skipped = 0
    for attempt_id, verdict, capture_rel in rows:
        cid = case_id(int(attempt_id))
        queue_path = label_root / "queue" / f"{cid}.json"
        labeled_path = label_root / "labeled" / f"{cid}.json"
        skipped_path = label_root / "skipped" / f"{cid}.json"
        if queue_path.exists() or labeled_path.exists() or skipped_path.exists():
            skipped += 1
            continue
        data = build_queue_case(int(attempt_id), verdict, capture_rel, claimcoin_root, label_root)
        queue_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        exported += 1
    print(f"exported={exported} skipped_existing={skipped} queue={label_root/'queue'}")


def prompt_yes_no_skip(prompt: str) -> str:
    while True:
        value = input(f"{prompt} [Y/n/skip]: ").strip().lower()
        if value in {"", "y", "yes"}:
            return "yes"
        if value in {"n", "no"}:
            return "no"
        if value in {"s", "skip"}:
            return "skip"
        print("Input valid: Y, n, atau skip")


def label_next(args: argparse.Namespace) -> None:
    label_root = Path(args.label_root)
    queue_files = sorted((label_root / "queue").glob("*.json"))
    if not queue_files:
        print("Queue kosong. Jalankan export dulu.")
        return
    queue_path = queue_files[0]
    data = json.loads(queue_path.read_text())
    cid = data["case_id"]
    print(f"\nCASE {cid} | attempt={data['attempt_id']} | verdict={data['verdict']} | options={data['option_count']}")
    print(f"Question image: {label_root / data['images']['question']}")
    print("Tesseract question OCR:")
    for item in data["current_solver"].get("tesseract_question_ocr", []):
        print(f"  - {item}")

    question_text = data["current_solver"].get("question_text") or ""
    action = prompt_yes_no_skip(f"Question solver read: {question_text!r}. Is this correct?")
    if action == "skip":
        print("Skipped. Case tetap di queue.")
        return
    if action == "no":
        question_text = input("Correct question text: ").strip()
    question_tokens = split_tokens(question_text, int(data["option_count"]))

    options_text: dict[str, str] = {}
    option_reviews: dict[str, bool] = {}
    for opt in data["images"]["options"]:
        oid = str(opt["id"])
        image_path = label_root / opt["image"]
        solver_text = data["current_solver"].get("options_text", {}).get(oid, "")
        raw_ocr = data["current_solver"].get("tesseract_option_ocr", {}).get(oid, [])
        print(f"\nOption {oid} image: {image_path}")
        print(f"Solver option read: {solver_text!r}")
        print(f"Raw OCR: {raw_ocr}")
        action = prompt_yes_no_skip("Is this option read correct?")
        if action == "skip":
            print("Skipped. Case tetap di queue.")
            return
        if action == "yes":
            correct = solver_text
            option_reviews[oid] = True
        else:
            correct = input(f"Correct text for option {oid}: ").strip()
            option_reviews[oid] = False
        options_text[oid] = correct

    derived_order = auto_order(question_text, options_text, int(data["option_count"]))
    submitted_order = [str(item) for item in data["current_solver"].get("submitted_answer_order", [])]
    print("\nQuestion:", question_text)
    print("Options:")
    for oid, text in options_text.items():
        print(f"  {oid} = {text}")
    print("Auto-derived order:", " ".join(derived_order) if derived_order else "<failed>")
    print("Solver submitted order:", " ".join(submitted_order))
    action = prompt_yes_no_skip("Is final order correct?")
    if action == "skip":
        print("Skipped. Case tetap di queue.")
        return
    if action == "yes":
        correct_order = derived_order or submitted_order
        order_correct = correct_order == submitted_order
    else:
        raw = input("Correct order ids separated by space/comma: ").replace(",", " ").split()
        correct_order = [str(item).strip() for item in raw if str(item).strip()]
        order_correct = False

    notes = input("Notes (optional): ").strip()
    data["status"] = "labeled"
    data["solver_review"] = {
        "question_read_correct": action != "no" and question_text == data["current_solver"].get("question_text"),
        "option_reads_correct": option_reviews,
        "submitted_order_correct": order_correct,
    }
    data["manual_label"] = {
        "question_text": question_text,
        "question_tokens": question_tokens,
        "options_text": options_text,
        "correct_answer_order": correct_order,
        "notes": notes,
    }
    labeled_path = label_root / "labeled" / queue_path.name
    labeled_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    queue_path.unlink()
    print(f"Saved labeled case: {labeled_path}")


def stats(args: argparse.Namespace) -> None:
    label_root = Path(args.label_root)
    for name in ["queue", "labeled", "skipped"]:
        print(f"{name}: {len(list((label_root/name).glob('*.json')))}")
    labeled = list((label_root / "labeled").glob("*.json"))
    if labeled:
        correct = 0
        for path in labeled:
            d = json.loads(path.read_text())
            if d.get("solver_review", {}).get("submitted_order_correct"):
                correct += 1
        print(f"solver submitted correct: {correct}/{len(labeled)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claimcoin-root", default=str(DEFAULT_CLAIMCOIN_ROOT))
    ap.add_argument("--label-root", default=str(DEFAULT_LABEL_ROOT))
    sub = ap.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--priority", choices=["rejected", "accepted", "all"], default="rejected")
    ex.add_argument("--limit", type=int, default=50)
    sub.add_parser("label-next")
    sub.add_parser("stats")
    args = ap.parse_args()
    if args.command == "export":
        export_cases(args)
    elif args.command == "label-next":
        label_next(args)
    elif args.command == "stats":
        stats(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
