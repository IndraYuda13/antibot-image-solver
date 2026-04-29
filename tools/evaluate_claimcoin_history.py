#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from antibot_image_solver.matcher import MatchEntry, solve_from_hypotheses  # noqa: E402
from antibot_image_solver.models import AntibotChallenge, OptionImage  # noqa: E402
from antibot_image_solver.normalize import canonical_forms  # noqa: E402
from antibot_image_solver.solver import solve_challenge  # noqa: E402


@dataclass
class Case:
    id: int
    account: str
    verdict: str
    capture_path: Path
    old_answer: list[str]


def load_cases(db_path: Path, capture_root: Path, limit: int | None, verdict_filter: str | None) -> list[Case]:
    con = sqlite3.connect(db_path)
    query = "select id,account,verdict,summary_json,capture_path from antibot_attempts order by id"
    cases: list[Case] = []
    for id_, account, verdict, summary_json, capture_path in con.execute(query):
        if verdict_filter and verdict != verdict_filter:
            continue
        summary = json.loads(summary_json)
        old = summary.get("antibotlinks")
        if not old:
            cap = json.loads((capture_root / capture_path).read_text())
            old = cap.get("solver", {}).get("antibotlinks")
        if not old:
            continue
        cases.append(Case(id_, account, verdict, capture_root / capture_path, str(old).split()))
        if limit and len(cases) >= limit:
            break
    return cases


def solve_stored_debug(case: Case) -> tuple[Case, list[str], float, list[str], str | None]:
    data = json.loads(case.capture_path.read_text())
    debug = data.get("solver", {}).get("debug") or {}
    entries: list[MatchEntry] = []
    for oid, cands in (debug.get("option_ocr") or {}).items():
        forms: set[str] = set()
        for cand in cands:
            forms |= canonical_forms(cand)
        entries.append(MatchEntry(id=str(oid), display=str(oid), candidates=list(cands), forms=forms))
    result = solve_from_hypotheses(debug.get("instruction_ocr") or [], entries)
    return case, result.ordered_ids, result.confidence, result.tokens_detected, None


def solve_full_ocr(case: Case) -> tuple[Case, list[str], float, list[str], str | None]:
    data = json.loads(case.capture_path.read_text())
    challenge = data["challenge"]
    ch = AntibotChallenge(
        instruction_image_base64=challenge["main_image"],
        options=[OptionImage(id=str(item["id"]), image_base64=item["image"]) for item in challenge["items"]],
        domain_hint=challenge.get("domain_hint") or "claimcoin",
    )
    result = solve_challenge(ch, debug=False)
    if not result.success:
        return case, [], result.confidence, result.tokens_detected, result.error_message
    return case, result.ordered_ids, result.confidence, result.tokens_detected, None


def render(status: dict, recent: list[str], start: float, total: int, mode: str) -> None:
    done = status["done"]
    accepted_total = status["accepted_total"]
    accepted_pass = status["accepted_pass"]
    accepted_fail = status["accepted_fail"]
    reject_total = status["reject_total"]
    reject_changed = status["reject_changed"]
    reject_same = status["reject_same"]
    errors = status["errors"]
    elapsed = max(0.001, time.time() - start)
    rate = done / elapsed
    eta = (total - done) / rate if rate else 0
    acc_rate = (accepted_pass / accepted_total * 100) if accepted_total else 0.0
    lower_bound = (accepted_pass / done * 100) if done else 0.0
    print("\033[2J\033[H", end="")
    print("ClaimCoin AntiBot historical evaluator")
    print("screen: shrtlnksolver")
    print(f"mode: {mode} | workers: {status['workers']} | total: {total}")
    print("-" * 72)
    print(f"progress: {done}/{total} ({done/total*100 if total else 0:.2f}%) | speed: {rate:.2f} case/s | ETA: {eta:.0f}s")
    print(f"accepted regression: {accepted_pass}/{accepted_total} pass | fail {accepted_fail} | accuracy {acc_rate:.2f}%")
    print(f"reject analysis: changed {reject_changed}/{reject_total} | still same {reject_same}")
    print(f"errors: {errors}")
    print(f"lower-bound current accuracy over processed labelled pass: {lower_bound:.2f}%")
    print("target: >95% accepted regression accuracy, then tune rejects with evidence")
    print("-" * 72)
    for line in recent[-18:]:
        print(line[:160])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/root/.openclaw/workspace/projects/claimcoin-autoclaim/state/claimcoin.sqlite3")
    ap.add_argument("--capture-root", default="/root/.openclaw/workspace/projects/claimcoin-autoclaim")
    ap.add_argument("--mode", choices=["stored-debug", "full-ocr"], default="stored-debug")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--verdict", choices=["accepted_success", "server_reject_antibot"])
    ap.add_argument("--output", default="/root/.openclaw/workspace/projects/antibot-image-solver/state/claimcoin-history-eval.jsonl")
    args = ap.parse_args()

    cases = load_cases(Path(args.db), Path(args.capture_root), args.limit, args.verdict)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    status = {
        "done": 0,
        "accepted_total": 0,
        "accepted_pass": 0,
        "accepted_fail": 0,
        "reject_total": 0,
        "reject_changed": 0,
        "reject_same": 0,
        "errors": 0,
        "workers": args.workers,
    }
    recent: list[str] = []
    lock = threading.Lock()
    start = time.time()
    solver = solve_full_ocr if args.mode == "full-ocr" else solve_stored_debug

    print(f"Loaded {len(cases)} cases. Starting {args.mode} with {args.workers} workers...")
    with out.open("w") as fh, cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(solver, c) for c in cases]
        for fut in cf.as_completed(futs):
            try:
                case, new_answer, conf, tokens, err = fut.result()
                changed = new_answer != case.old_answer
                if err:
                    label = "ERROR"
                    status["errors"] += 1
                elif case.verdict == "accepted_success":
                    status["accepted_total"] += 1
                    if not changed:
                        status["accepted_pass"] += 1
                        label = "PASS"
                    else:
                        status["accepted_fail"] += 1
                        label = "FAIL"
                else:
                    status["reject_total"] += 1
                    if changed:
                        status["reject_changed"] += 1
                        label = "REJECT_CHANGED"
                    else:
                        status["reject_same"] += 1
                        label = "REJECT_SAME"
                rec = {
                    "id": case.id,
                    "verdict": case.verdict,
                    "label": label,
                    "old_answer": case.old_answer,
                    "new_answer": new_answer,
                    "confidence": conf,
                    "tokens": tokens,
                    "error": err,
                }
            except Exception as e:
                status["errors"] += 1
                rec = {"label": "ERROR", "error": repr(e)}
                label = "ERROR"
                case = Case(-1, "", "", Path(""), [])
                new_answer = []
            with lock:
                status["done"] += 1
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                if label == "PASS":
                    line = f"Test #{case.id} passed | {case.verdict} | answer={' '.join(new_answer)} | success rate {status['accepted_pass']}/{status['accepted_total']}"
                elif label == "FAIL":
                    line = f"Test #{case.id} FAILED | old={' '.join(case.old_answer)} new={' '.join(new_answer)} | conf={rec.get('confidence')}"
                else:
                    line = f"Test #{case.id} {label} | old={' '.join(case.old_answer)} new={' '.join(new_answer)} | conf={rec.get('confidence')}"
                recent.append(line)
                if status["done"] == len(cases) or status["done"] % 3 == 0:
                    render(status, recent, start, len(cases), args.mode)
    render(status, recent, start, len(cases), args.mode)
    print("\nOutput:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
