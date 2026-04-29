#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from antibot_image_solver.matcher import MatchEntry, solve_from_hypotheses
from antibot_image_solver.normalize import canonical_forms


@dataclass
class Case:
    id: int
    verdict: str
    capture_path: Path
    old_answer: list[str]


def load_cases(db: Path, root: Path, mode: str, limit: int | None) -> list[Case]:
    con = sqlite3.connect(db)
    if mode == "accepted_fail_ids":
        ids = [9, 35, 52, 63, 98, 184, 196, 278, 291, 298, 321, 323, 326, 330, 345, 397, 406, 415, 424]
        q = "select id,verdict,capture_path from antibot_attempts where id=?"
        rows = []
        for id_ in ids:
            row = con.execute(q, (id_,)).fetchone()
            if row:
                rows.append(row)
    elif mode == "rejects":
        rows = list(con.execute("select id,verdict,capture_path from antibot_attempts where verdict='server_reject_antibot' order by id"))
    elif mode == "latest_accepted":
        rows = list(con.execute("select id,verdict,capture_path from antibot_attempts where verdict='accepted_success' order by id desc limit ?", (limit or 80,)))
        rows.reverse()
    else:
        rows = list(con.execute("select id,verdict,capture_path from antibot_attempts order by id"))
        if limit:
            rows = rows[:limit]
    cases = []
    for id_, verdict, rel in rows:
        data = json.loads((root / rel).read_text())
        answer = str(data.get("solver", {}).get("antibotlinks") or "").split()
        if answer:
            cases.append(Case(id_, verdict, root / rel, answer))
    return cases


def make_ocr():
    import ddddocr
    return ddddocr.DdddOcr(show_ad=False)


def ocr_image(ocr, b64: str) -> str:
    try:
        return str(ocr.classification(base64.b64decode(b64)) or "").strip()
    except Exception as exc:
        return f"ERR:{exc}"


def solve_case(case: Case) -> dict:
    ocr = make_ocr()
    data = json.loads(case.capture_path.read_text())
    challenge = data["challenge"]
    instruction = ocr_image(ocr, challenge["main_image"])
    entries = []
    option_ocr = {}
    for item in challenge["items"]:
        text = ocr_image(ocr, item["image"])
        option_ocr[str(item["id"])] = [text]
        entries.append(MatchEntry(id=str(item["id"]), display=text, candidates=[text], forms=canonical_forms(text)))
    try:
        outcome = solve_from_hypotheses([instruction], entries)
        new = outcome.ordered_ids
        conf = outcome.confidence
        err = None
        tokens = outcome.tokens_detected
        best = outcome.best_score
        second = outcome.second_best_score
    except Exception as exc:
        new = []
        conf = 0.0
        err = repr(exc)
        tokens = []
        best = second = 0
    return {
        "id": case.id,
        "verdict": case.verdict,
        "old_answer": case.old_answer,
        "new_answer": new,
        "changed": new != case.old_answer,
        "accepted_pass": case.verdict == "accepted_success" and new == case.old_answer,
        "instruction_ocr": instruction,
        "option_ocr": option_ocr,
        "confidence": conf,
        "tokens": tokens,
        "best_score": best,
        "second_best_score": second,
        "error": err,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/root/.openclaw/workspace/projects/claimcoin-autoclaim/state/claimcoin.sqlite3")
    ap.add_argument("--root", default="/root/.openclaw/workspace/projects/claimcoin-autoclaim")
    ap.add_argument("--mode", choices=["accepted_fail_ids", "rejects", "latest_accepted", "all"], default="accepted_fail_ids")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--output", default="state/ddddocr-benchmark.jsonl")
    args = ap.parse_args()

    cases = load_cases(Path(args.db), Path(args.root), args.mode, args.limit)
    out = ROOT / args.output
    out.parent.mkdir(exist_ok=True)
    done = passed = changed = errors = 0
    start = time.time()
    recent = []
    print(f"ddddocr ClaimCoin benchmark | mode={args.mode} | cases={len(cases)} | workers={args.workers}", flush=True)
    with out.open("w") as fh, cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(solve_case, case) for case in cases]
        for fut in cf.as_completed(futs):
            rec = fut.result()
            done += 1
            if rec["accepted_pass"]:
                passed += 1
                label = "PASS"
            elif rec["error"]:
                errors += 1
                label = "ERROR"
            elif rec["changed"]:
                changed += 1
                label = "CHANGED"
            else:
                label = "SAME"
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            rate = done / max(0.001, time.time() - start)
            recent.append(f"Test #{rec['id']} {label} old={' '.join(rec['old_answer'])} new={' '.join(rec['new_answer'])} instr={rec['instruction_ocr']!r}")
            print("\033[2J\033[H", end="")
            print(f"ddddocr ClaimCoin benchmark | mode={args.mode} | workers={args.workers}")
            print(f"progress {done}/{len(cases)} | speed {rate:.2f}/s")
            print(f"accepted-pass {passed} | changed {changed} | errors {errors}")
            print(f"output {out}")
            print("-" * 80)
            for line in recent[-20:]:
                print(line[:180])
    print(f"DONE output={out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
