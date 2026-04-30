#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from html import escape
import secrets
import sqlite3
import subprocess
import threading
import time
import uuid
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from antibot_image_solver.models import AntibotChallenge, OptionImage  # noqa: E402
from antibot_image_solver.solver import solve_challenge  # noqa: E402
from label_claimcoin_antibot import (  # noqa: E402
    DEFAULT_CLAIMCOIN_ROOT,
    DEFAULT_LABEL_ROOT,
    auto_order,
    best_text,
    build_queue_case,
    load_capture,
    split_tokens,
)

CLAIMCOIN_ROOT = DEFAULT_CLAIMCOIN_ROOT
LABEL_ROOT = DEFAULT_LABEL_ROOT
TOKEN_PATH = LABEL_ROOT / "web_auth_token.txt"
JOB_STATUS_PATH = LABEL_ROOT / "jobs" / "solver_eval_status.json"
JOB_STOP_PATH = LABEL_ROOT / "jobs" / "solver_eval_stop.flag"
JOB_REPORTS_DIR = LABEL_ROOT / "jobs" / "reports"
JOB_LOCK = threading.Lock()
JOB_THREAD: threading.Thread | None = None

app = FastAPI(title="ClaimCoin AntiBot Label Studio")


def ensure_dirs() -> None:
    for sub in ["queue", "labeled", "skipped", "images", "preview", "web", "jobs", "jobs/reports"]:
        (LABEL_ROOT / sub).mkdir(parents=True, exist_ok=True)


def get_token() -> str:
    ensure_dirs()
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    token = secrets.token_urlsafe(24)
    TOKEN_PATH.write_text(token)
    TOKEN_PATH.chmod(0o600)
    return token


def authed(request: Request) -> bool:
    token = get_token()
    supplied = request.query_params.get("token") or request.cookies.get("label_token") or request.headers.get("x-label-token")
    return bool(supplied and secrets.compare_digest(str(supplied), token))


def require_auth(request: Request) -> None:
    if not authed(request):
        raise HTTPException(status_code=403, detail="missing or invalid token")


def token_q(request: Request) -> str:
    token = request.query_params.get("token") or request.cookies.get("label_token") or get_token()
    return urlencode({"token": token})


def html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#0c0f0e;--panel:#141a17;--panel2:#1c241f;--ink:#edf7ee;--muted:#9fb5a6;--line:#2d3a32;--accent:#b6ff6a;--warn:#ffcf5a;--bad:#ff6b6b;--good:#60ffa8}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at top left,#1a2b20,#0c0f0e 42%);color:var(--ink);font:15px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
a{{color:var(--accent)}} .wrap{{max-width:1220px;margin:0 auto;padding:24px}} .top{{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:20px;flex-wrap:wrap}}
h1{{font-size:28px;margin:0;letter-spacing:-.04em}} h2{{margin:0 0 10px}} .tag{{color:var(--muted);font-size:13px}}
.card{{background:linear-gradient(180deg,var(--panel),#101511);border:1px solid var(--line);border-radius:18px;padding:18px;margin:14px 0;box-shadow:0 18px 60px #0008}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}} .stat{{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:14px}}
.stat b{{font-size:28px;color:var(--accent)}} button,.btn{{background:var(--accent);color:#071008;border:0;border-radius:12px;padding:10px 14px;font-weight:800;cursor:pointer;text-decoration:none;display:inline-block}}
.stat.good b{{color:var(--good)}} .stat.bad b{{color:var(--bad)}} .stat.warn b{{color:var(--warn)}}
.btn2{{background:#233027;color:var(--ink);border:1px solid var(--line)}} .danger{{background:var(--bad);color:#200}}
input,textarea,select{{width:100%;background:#0b100d;color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit}}
label{{display:block;color:var(--muted);font-size:12px;margin:9px 0 5px}} img{{max-width:100%;background:white;border-radius:10px;border:1px solid #334}}
.case-list{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}} .pill{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;color:var(--muted);font-size:12px}}
.option{{display:grid;grid-template-columns:210px 1fr;gap:14px;align-items:start;border-top:1px solid var(--line);padding-top:14px;margin-top:14px}}
pre{{white-space:pre-wrap;color:#cfe6d2;background:#09100c;border:1px solid var(--line);padding:10px;border-radius:10px;max-height:170px;overflow:auto}}
.small{{font-size:12px;color:var(--muted)}} .ok{{color:var(--good)}} .bad{{color:var(--bad)}} .warn{{color:var(--warn)}}
.help{{border:1px solid #405342;background:#101a13;border-radius:14px;padding:12px;color:#cfe6d2;margin:10px 0}}
.help b{{color:var(--accent)}} .ocr-box{{opacity:.78}} .ocr-box summary{{cursor:pointer;color:var(--muted)}}
.order-board{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} .chipbox{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;min-height:54px;padding:12px;background:#0b100d;border:1px solid var(--line);border-radius:14px}}
.order-chip{{background:#d7ff92;color:#071008;border:0;border-radius:999px;padding:10px 13px;font-weight:900;cursor:pointer;box-shadow:0 8px 22px #0008}}
.order-chip.used{{opacity:.35;filter:grayscale(1)}} .answer-slot{{display:flex;gap:8px;align-items:center;background:#1f2b23;border:1px solid #3e5144;border-radius:999px;padding:7px 10px}}
.changed-note{{display:none;color:var(--warn);font-size:12px;margin-top:5px}} .field-changed .changed-note{{display:block}}
.progress{{height:16px;background:#09100c;border:1px solid var(--line);border-radius:999px;overflow:hidden}} .progress span{{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--good));width:0}}
.toast{{position:fixed;right:18px;bottom:18px;background:#d7ff92;color:#071008;border-radius:14px;padding:12px 14px;font-weight:900;box-shadow:0 18px 60px #000b;opacity:0;transform:translateY(10px);transition:.18s;z-index:9999}} .toast.show{{opacity:1;transform:translateY(0)}}
.answer-slot button{{padding:2px 7px;border-radius:999px;background:#ff6b6b;color:#230000}} .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
@media(max-width:720px){{.option,.order-board{{grid-template-columns:1fr}}.wrap{{padding:14px}}}}
</style></head><body><div class="wrap">{body}</div></body></html>"""


def queue_files() -> list[Path]:
    ensure_dirs()
    return sorted((LABEL_ROOT / "queue").glob("*.json"))


def labeled_files() -> list[Path]:
    ensure_dirs()
    return sorted((LABEL_ROOT / "labeled").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def load_case(case_id: str) -> tuple[Path, dict[str, Any]]:
    path = LABEL_ROOT / "queue" / f"{case_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="case not found in queue")
    return path, json.loads(path.read_text())


def load_labeled(case_id: str) -> tuple[Path, dict[str, Any]]:
    path = LABEL_ROOT / "labeled" / f"{case_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="case not found in labeled")
    return path, json.loads(path.read_text())


def pct(part: int, total: int) -> float:
    return round((part / total) * 100, 2) if total else 0.0


def stats_data() -> dict[str, Any]:
    ensure_dirs()
    con = sqlite3.connect(CLAIMCOIN_ROOT / "state" / "claimcoin.sqlite3")
    total = con.execute("select count(*) from antibot_attempts").fetchone()[0]
    accepted = con.execute("select count(*) from antibot_attempts where verdict='accepted_success'").fetchone()[0]
    rejected = con.execute("select count(*) from antibot_attempts where verdict='server_reject_antibot'").fetchone()[0]
    errors = total - accepted - rejected
    return {
        "queue": len(list((LABEL_ROOT / "queue").glob("*.json"))),
        "labeled": len(list((LABEL_ROOT / "labeled").glob("*.json"))),
        "skipped": len(list((LABEL_ROOT / "skipped").glob("*.json"))),
        "raw_total": total,
        "raw_accepted": accepted,
        "raw_rejected": rejected,
        "raw_errors": errors,
        "raw_success_rate": pct(accepted, total),
    }


def verdict_stats(where: str = "1=1", params: tuple[Any, ...] = ()) -> dict[str, Any]:
    con = sqlite3.connect(CLAIMCOIN_ROOT / "state" / "claimcoin.sqlite3")
    rows = dict(con.execute(f"select verdict,count(*) from antibot_attempts where {where} group by verdict", params).fetchall())
    total = sum(rows.values())
    accepted = int(rows.get("accepted_success", 0))
    rejected = int(rows.get("server_reject_antibot", 0))
    errors = total - accepted - rejected
    return {"total": total, "accepted": accepted, "rejected": rejected, "errors": errors, "success_rate": pct(accepted, total)}


def solver_stats_data() -> dict[str, Any]:
    con = sqlite3.connect(CLAIMCOIN_ROOT / "state" / "claimcoin.sqlite3")
    max_id = con.execute("select coalesce(max(id),0) from antibot_attempts").fetchone()[0]
    return {
        "overall": verdict_stats(),
        "last_100": verdict_stats("id > ?", (max(0, max_id - 100),)),
        "post_tuning_1013": verdict_stats("id >= ?", (1013,)),
        "max_id": max_id,
    }


def label_eval_data() -> dict[str, Any]:
    total = exact = corrected = incomplete = 0
    for path in labeled_files():
        data = json.loads(path.read_text())
        total += 1
        solver_order = [str(x) for x in (data.get("current_solver", {}).get("submitted_answer_order") or [])]
        label_order = [str(x) for x in ((data.get("manual_label") or {}).get("correct_answer_order") or [])]
        if not label_order:
            incomplete += 1
        elif solver_order == label_order:
            exact += 1
        else:
            corrected += 1
    checked = total - incomplete
    return {"total": total, "checked": checked, "solver_exact": exact, "corrected": corrected, "incomplete": incomplete, "label_success_rate": pct(exact, checked)}


def job_status_data() -> dict[str, Any]:
    return current_job_status()




def write_job_status(payload: dict[str, Any]) -> None:
    ensure_dirs()
    payload = {**payload, "updated_at": time.time()}
    JOB_STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def current_job_status() -> dict[str, Any]:
    ensure_dirs()
    if JOB_STATUS_PATH.exists():
        try:
            return json.loads(JOB_STATUS_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"status": "idle", "kind": None, "progress": 0, "message": "Belum ada job aktif.", "updated_at": None}


def case_id_from_attempt(attempt_id: int) -> str:
    return f"claimcoin_{attempt_id:06d}"


def accepted_ground_truth_from_capture(capture_rel: str) -> list[str]:
    capture = load_capture(CLAIMCOIN_ROOT / capture_rel)
    solver = capture.get("solver") or {}
    order = solver.get("ordered_ids") or str(solver.get("antibotlinks") or "").split()
    return [str(x) for x in order]


def build_eval_cases(include_accepted: bool, include_labeled: bool, accepted_limit: int | None = None) -> list[dict[str, Any]]:
    ensure_dirs()
    cases: list[dict[str, Any]] = []
    labeled_ids = {p.stem for p in labeled_files()}
    if include_accepted:
        con = sqlite3.connect(CLAIMCOIN_ROOT / "state" / "claimcoin.sqlite3")
        query = "select id, capture_path from antibot_attempts where verdict='accepted_success' order by id asc"
        rows = list(con.execute(query))
        if accepted_limit:
            rows = rows[:accepted_limit]
        for attempt_id, capture_rel in rows:
            cid = case_id_from_attempt(int(attempt_id))
            if cid in labeled_ids:
                continue
            cases.append({
                "case_id": cid,
                "source": "accepted_success_raw",
                "source_capture_path": capture_rel,
                "expected_order": accepted_ground_truth_from_capture(capture_rel),
            })
    if include_labeled:
        for path in labeled_files():
            data = json.loads(path.read_text())
            expected = [str(x) for x in ((data.get("manual_label") or {}).get("correct_answer_order") or [])]
            if not expected:
                continue
            cases.append({
                "case_id": data.get("case_id") or path.stem,
                "source": "manual_label",
                "source_capture_path": data.get("source_capture_path"),
                "expected_order": expected,
            })
    return cases



def latest_solver_payload_subprocess(data: dict[str, Any], timeout_seconds: int = 75, eval_mode: str = "current-ocr") -> dict[str, Any]:
    capture_rel = data.get("source_capture_path")
    if not capture_rel:
        raise RuntimeError("case has no source capture path")
    capture_path = CLAIMCOIN_ROOT / str(capture_rel)
    if not capture_path.exists():
        raise RuntimeError(f"source capture not found: {capture_path}")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "claimcoin_eval_one.py"), str(capture_path), "--mode", eval_mode],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()[-1000:])
    return json.loads(proc.stdout)

def eval_one_item(item: dict[str, Any], *, eval_mode: str = "current-ocr") -> dict[str, Any]:
    timeout = 20 if eval_mode == "stored-debug" else 75
    latest = latest_solver_payload_subprocess(item, timeout_seconds=timeout, eval_mode=eval_mode)
    actual = [str(x) for x in (latest.get("submitted_answer_order") or [])]
    expected = [str(x) for x in (item.get("expected_order") or [])]
    passed = bool(expected) and actual == expected
    return {
        "case_id": item["case_id"],
        "source": item["source"],
        "expected_order": expected,
        "actual_order": actual,
        "pass": passed,
        "confidence": latest.get("confidence"),
        "question_text": latest.get("question_text"),
        "options_text": latest.get("options_text"),
        "error": None,
    }


def source_totals(cases: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for item in cases:
        src = item["source"]
        out.setdefault(src, {"total": 0, "done": 0, "ok": 0, "wrong": 0, "errors": 0})
        out[src]["total"] += 1
    return out


def live_system_load() -> dict[str, Any]:
    try:
        load1, load5, load15 = os.getloadavg()
        return {"load1": round(load1, 2), "load5": round(load5, 2), "load15": round(load15, 2), "cpu_count": os.cpu_count()}
    except OSError:
        return {"cpu_count": os.cpu_count()}


def run_eval_job(
    job_id: str,
    *,
    include_accepted: bool,
    include_labeled: bool,
    accepted_limit: int | None = None,
    workers: int = 2,
    eval_mode: str = "stored-debug",
) -> None:
    JOB_STOP_PATH.unlink(missing_ok=True)
    started = time.time()
    workers = max(1, min(int(workers or 2), 3))
    eval_mode = eval_mode if eval_mode in {"stored-debug", "current-ocr"} else "stored-debug"
    try:
        cases = build_eval_cases(include_accepted, include_labeled, accepted_limit)
        total = len(cases)
        ok = wrong = errors = done = 0
        by_source = source_totals(cases)
        failures: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        running_cases: dict[concurrent.futures.Future, dict[str, Any]] = {}
        report_path = JOB_REPORTS_DIR / f"{job_id}.json"

        def status_payload(message: str, *, status: str = "running", can_stop: bool = True) -> dict[str, Any]:
            return {
                "job_id": job_id,
                "status": status,
                "kind": "stable_eval",
                "progress": int((done / total) * 100) if total else 100,
                "message": message,
                "total": total,
                "done": done,
                "remaining": max(total - done, 0),
                "running": len(running_cases),
                "running_cases": [item.get("case_id") for item in running_cases.values()],
                "workers": workers,
                "ok": ok,
                "wrong": wrong,
                "errors": errors,
                "success_rate": pct(ok, done),
                "by_source": by_source,
                "failures_sample": failures,
                "report_path": str(report_path),
                "can_stop": can_stop,
                "system_load": live_system_load(),
                "eval_mode": eval_mode,
            }

        write_job_status(status_payload(f"Prepared {total} cases. Starting {workers}-worker {eval_mode} eval..."))
        next_index = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            while (next_index < total or running_cases) and not JOB_STOP_PATH.exists():
                while next_index < total and len(running_cases) < workers and not JOB_STOP_PATH.exists():
                    item = cases[next_index]
                    fut = executor.submit(eval_one_item, item, eval_mode=eval_mode)
                    running_cases[fut] = item
                    next_index += 1
                write_job_status(status_payload(f"Running {len(running_cases)} case(s), done {done}/{total}: ok={ok}, wrong={wrong}, errors={errors}"))
                if not running_cases:
                    break
                finished, _ = concurrent.futures.wait(running_cases.keys(), timeout=3, return_when=concurrent.futures.FIRST_COMPLETED)
                for fut in finished:
                    item = running_cases.pop(fut)
                    source = item["source"]
                    done += 1
                    by_source[source]["done"] += 1
                    try:
                        result = fut.result()
                        if result.get("pass"):
                            ok += 1
                            by_source[source]["ok"] += 1
                        else:
                            wrong += 1
                            by_source[source]["wrong"] += 1
                            if len(failures) < 80:
                                failures.append({
                                    "case_id": result.get("case_id"),
                                    "source": source,
                                    "expected_order": result.get("expected_order"),
                                    "actual_order": result.get("actual_order"),
                                    "confidence": result.get("confidence"),
                                    "question_text": result.get("question_text"),
                                    "options_text": result.get("options_text"),
                                })
                        results.append(result)
                    except Exception as exc:
                        errors += 1
                        by_source[source]["errors"] += 1
                        err = {"case_id": item.get("case_id"), "source": source, "error": type(exc).__name__, "message": str(exc)}
                        results.append({**err, "pass": False})
                        if len(failures) < 80:
                            failures.append(err)
                    if done % 3 == 0 or done == total:
                        write_job_status(status_payload(f"Evaluated {done}/{total}: ok={ok}, wrong={wrong}, errors={errors}"))

            if JOB_STOP_PATH.exists():
                write_job_status(status_payload("Stop requested. Waiting currently running case(s) to timeout/finish...", can_stop=False))
                for fut, item in list(running_cases.items()):
                    try:
                        result = fut.result(timeout=90)
                        source = item["source"]
                        done += 1
                        by_source[source]["done"] += 1
                        if result.get("pass"):
                            ok += 1
                            by_source[source]["ok"] += 1
                        else:
                            wrong += 1
                            by_source[source]["wrong"] += 1
                        results.append(result)
                    except Exception as exc:
                        source = item["source"]
                        done += 1
                        by_source[source]["done"] += 1
                        errors += 1
                        by_source[source]["errors"] += 1
                        err = {"case_id": item.get("case_id"), "source": source, "error": type(exc).__name__, "message": str(exc)}
                        results.append({**err, "pass": False})
                        if len(failures) < 80:
                            failures.append(err)
                write_job_status(status_payload("Stopped by user.", status="stopped", can_stop=False))
                return

        summary = {
            "job_id": job_id,
            "status": "completed",
            "kind": "stable_eval",
            "started_at": started,
            "finished_at": time.time(),
            "total": total,
            "done": done,
            "workers": workers,
            "ok": ok,
            "wrong": wrong,
            "errors": errors,
            "success_rate": pct(ok, done),
            "by_source": by_source,
            "failures_sample": failures,
            "results": results,
            "system_load": live_system_load(),
            "eval_mode": eval_mode,
        }
        report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        write_job_status({
            **{k: v for k, v in summary.items() if k != "results"},
            "progress": 100,
            "remaining": 0,
            "running": 0,
            "running_cases": [],
            "message": f"Completed {done}: success={pct(ok, done)}%, wrong={wrong}, errors={errors}",
            "report_path": str(report_path),
            "can_stop": False,
        })
    except Exception as exc:
        write_job_status({
            "job_id": job_id,
            "status": "error",
            "kind": "stable_eval",
            "progress": 0,
            "message": f"Job error: {type(exc).__name__}: {exc}",
            "can_stop": False,
        })

def latest_solver_payload(data: dict[str, Any]) -> dict[str, Any]:
    capture_rel = data.get("source_capture_path")
    if not capture_rel:
        raise HTTPException(status_code=400, detail="case has no source capture path")
    capture_path = CLAIMCOIN_ROOT / str(capture_rel)
    if not capture_path.exists():
        raise HTTPException(status_code=404, detail="source capture not found")
    capture = load_capture(capture_path)
    challenge = capture.get("challenge") or {}
    items = challenge.get("items") or []
    solver_input = AntibotChallenge(
        instruction_image_base64=str(challenge.get("main_image") or ""),
        options=[OptionImage(id=str(item.get("id")), image_base64=str(item.get("image") or "")) for item in items],
        domain_hint=str(challenge.get("domain_hint") or "claimcoin"),
        request_id=str(data.get("case_id") or capture.get("attempt_id") or ""),
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

def image_url(image_path: str, q: str) -> str:
    return f"/images/{image_path.replace('images/', '')}?{q}"


def option_preview(data: dict[str, Any], q: str) -> str:
    parts = []
    for opt in data["images"]["options"]:
        oid = str(opt["id"])
        parts.append(f"<div><img src='{image_url(opt['image'], q)}' style='max-height:78px'><div class='pill'>ID {oid}</div></div>")
    return "".join(parts)


@app.middleware("http")
async def token_cookie(request: Request, call_next):
    response = await call_next(request)
    token = request.query_params.get("token")
    if token and secrets.compare_digest(token, get_token()):
        response.set_cookie("label_token", token, httponly=True, samesite="lax")
    return response


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> str:
    require_auth(request)
    q = token_q(request)
    st = stats_data()
    cases = []
    for path in queue_files()[:60]:
        data = json.loads(path.read_text())
        cases.append(f"""<div class='card'><div><b>{data['case_id']}</b></div>
        <div class='small'>attempt {data['attempt_id']} • {data['verdict']} • options {data['option_count']}</div>
        <div class='small'>solver question: {escape(data['current_solver'].get('question_text',''))}</div>
        <p><a class='btn btn2' href='/case/{data['case_id']}?{q}'>Label case</a></p></div>""")
    body = f"""
    <div class='top'><div><h1>ClaimCoin AntiBot Label Studio</h1><div class='tag'>private tunnel UI • raw captures preserved</div></div><div><a class='btn btn2' href='/stats?{q}'>Solver stats</a> <a class='btn btn2' href='/gallery?{q}'>Gallery</a> <a class='btn btn2' href='/labeled?{q}'>Review labels</a></div></div>
    <div class='grid'>
      <div class='stat'><span>Queue</span><br><b>{st['queue']}</b></div><div class='stat'><span>Labeled</span><br><b>{st['labeled']}</b></div><div class='stat good'><span>Success rate</span><br><b>{st['raw_success_rate']}%</b></div><div class='stat'><span>Raw total</span><br><b>{st['raw_total']}</b></div>
    </div>
    <div class='card'><h2>Tambah queue</h2><form method='post' action='/export?{q}'><div class='grid'><div><label>Priority</label><select name='priority'><option value='rejected'>Rejected dulu</option><option value='accepted'>Accepted</option><option value='all'>All</option></select></div><div><label>Limit</label><input name='limit' value='50'></div></div><p><button>Export ke queue</button></p></form></div>
    <h2>Queue</h2><div class='case-list'>{''.join(cases) or '<div class=card>Queue kosong.</div>'}</div>
    """
    return html_page("ClaimCoin Label Studio", body)


@app.post("/export")
def export(request: Request, priority: str = Form("rejected"), limit: int = Form(50)) -> RedirectResponse:
    require_auth(request)
    ensure_dirs()
    con = sqlite3.connect(CLAIMCOIN_ROOT / "state" / "claimcoin.sqlite3")
    where = "verdict='server_reject_antibot'" if priority == "rejected" else ("verdict='accepted_success'" if priority == "accepted" else "1=1")
    rows = list(con.execute(f"select id,verdict,capture_path from antibot_attempts where {where} order by id desc limit ?", (int(limit),)))
    rows.reverse()
    for attempt_id, verdict, capture_rel in rows:
        cid = f"claimcoin_{int(attempt_id):06d}"
        targets = [LABEL_ROOT / sub / f"{cid}.json" for sub in ["queue", "labeled", "skipped"]]
        if any(p.exists() for p in targets):
            continue
        data = build_queue_case(int(attempt_id), verdict, capture_rel, CLAIMCOIN_ROOT, LABEL_ROOT)
        (LABEL_ROOT / "queue" / f"{cid}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return RedirectResponse(f"/?{token_q(request)}", status_code=303)


@app.get("/images/{path:path}")
def image(path: str, request: Request) -> Response:
    require_auth(request)
    file = (LABEL_ROOT / "images" / path).resolve()
    if not str(file).startswith(str((LABEL_ROOT / "images").resolve())) or not file.exists():
        raise HTTPException(status_code=404)
    return Response(file.read_bytes(), media_type="image/png")


@app.get("/case/{case_id}/latest-solver")
def latest_solver(case_id: str, request: Request) -> dict[str, Any]:
    require_auth(request)
    _, data = load_case(case_id)
    try:
        return latest_solver_payload(data)
    except HTTPException:
        raise
    except Exception as exc:
        return {"success": False, "status": "error", "error_code": type(exc).__name__, "error_message": str(exc)}


@app.get("/case/{case_id}", response_class=HTMLResponse)
def case_page(case_id: str, request: Request) -> str:
    require_auth(request)
    q = token_q(request)
    _, data = load_case(case_id)
    current = data["current_solver"]
    ml = data.get("manual_label") or {}
    question_value = ml.get("question_text") or current.get("question_text") or ""
    opts_html = []
    option_ids = [str(opt["id"]) for opt in data["images"]["options"]]
    for opt in data["images"]["options"]:
        oid = str(opt["id"])
        rel = opt["image"].replace("images/", "")
        solver_text = current.get("options_text", {}).get(oid, "")
        value = (ml.get("options_text") or {}).get(oid) or solver_text
        raw = current.get("tesseract_option_ocr", {}).get(oid, [])
        opts_html.append(f"""<div class='option'><div><img src='/images/{rel}?{q}'><div class='pill'>ID {oid}</div></div><div>
        <label>Final option text, edit this if the image text is different</label><input class='watched-field option-field' data-original='{escape(solver_text)}' data-check='option_correct_{oid}' name='option_{oid}' value='{escape(value)}'>
        <div class='changed-note'>Edited manually, checkbox auto-unchecked.</div>
        <p><button type='button' class='btn btn2 use-solver-text' data-target='option_{oid}' data-value='{escape(solver_text)}'>Pakai hasil solver text</button></p>
        <label><input id='option_correct_{oid}' type='checkbox' name='option_correct_{oid}' value='1' checked style='width:auto'> solver read correct, auto-unchecked if you edit this option</label>
        <details class='ocr-box'><summary>OCR candidate list, read-only evidence</summary><pre>{escape(json.dumps(raw, ensure_ascii=False, indent=2))}</pre></details></div></div>""")
    submitted = current.get("submitted_answer_order") or []
    order_value = " ".join(ml.get("correct_answer_order") or submitted)
    question_rel = data["images"]["question"].replace("images/", "")
    option_buttons = "".join([f"<button type='button' class='order-chip' data-id='{escape(oid)}'>ID {escape(oid)}</button>" for oid in option_ids])
    body = f"""
    <div class='top'><div><h1>{data['case_id']}</h1><div class='tag'>attempt {data['attempt_id']} • {data['verdict']} • confidence {current.get('confidence')}</div></div><a class='btn btn2' href='/?{q}'>Back</a></div>
    <div class='card'><h2>Latest tuned solver</h2><div class='help'>Klik ini untuk rerun solver versi kode terbaru dari raw capture. Ini bukan nilai lama dari queue JSON.</div><p><button type='button' class='btn' id='run-latest-solver'>Run latest solver</button> <button type='button' class='btn btn2' id='apply-latest-solver' disabled>Apply latest result to fields</button></p><pre id='latest-solver-box'>Belum dijalankan.</pre></div>
    <form method='post' action='/case/{case_id}/save?{q}'>
    <div class='card'><h2>Question</h2><div class='help'><b>Yang diedit: Final question text.</b> List OCR di bawah itu cuma kandidat bacaan mentah. Kalau gambar memang bertulis <span class='mono'>rat, bat, owl</span>, isi field ini dengan <span class='mono'>rat, bat, owl</span>. Jangan edit list mentahnya.</div><img src='/images/{question_rel}?{q}'><label>Final question text</label><input class='watched-field' data-original='{escape(current.get('question_text') or '')}' data-check='question_correct' name='question_text' value='{escape(question_value)}'>
    <div class='changed-note'>Edited manually, checkbox auto-unchecked.</div>
    <p><button type='button' class='btn btn2 use-solver-text' data-target='question_text' data-value='{escape(current.get('question_text') or '')}'>Pakai hasil solver question</button></p>
    <label><input id='question_correct' type='checkbox' name='question_correct' value='1' checked style='width:auto'> solver question read correct, auto-unchecked if you edit the final question text</label>
    <details class='ocr-box'><summary>OCR candidate list, read-only evidence</summary><pre>{escape(json.dumps(current.get('tesseract_question_ocr', []), ensure_ascii=False, indent=2))}</pre></details></div>
    <div class='card'><h2>Options</h2>{''.join(opts_html)}</div>
    <div class='card'><h2>Final answer order</h2><div class='help'><b>Klik ID option sesuai urutan jawaban yang benar.</b> Contoh kalau benar <span class='mono'>2650 8668 4887</span>, klik ID 2650, lalu 8668, lalu 4887. Bisa reset kapan aja.</div>
    <div class='small'>Solver submitted: {' '.join(submitted)}</div>
    <div class='order-board'><div><label>Available option IDs</label><div id='available-options' class='chipbox'>{option_buttons}</div></div><div><label>Your selected order</label><div id='selected-order' class='chipbox'></div></div></div>
    <input type='hidden' id='correct_order' name='correct_order' value='{escape(order_value)}'>
    <p><button type='button' class='btn btn2' id='use-solver-order'>Pakai order solver</button> <button type='button' class='btn btn2' id='reset-order'>Reset order</button></p>
    <label><input type='checkbox' name='submitted_order_correct' value='1' style='width:auto'> submitted order already correct</label>
    <label>Notes</label><textarea name='notes' rows='3'>{escape(ml.get('notes',''))}</textarea>
    <p><button>Save as labeled</button> <a class='btn btn2' href='/?{q}'>Skip, keep in queue</a></p></div></form>
<div id='toast' class='toast'></div>
<script>
const optionIds = {json.dumps(option_ids)};
const solverTexts = {json.dumps(current.get('options_text', {}))};
const solverOrder = {json.dumps(submitted)};
const latestSolverUrl = "/case/{case_id}/latest-solver?{q}";
let latestResult = null;
const initialOrder = {json.dumps(order_value.split())};
const hidden = document.getElementById('correct_order');
const selected = document.getElementById('selected-order');
const chips = Array.from(document.querySelectorAll('.order-chip'));
let order = [];
function renderOrder() {{
  selected.innerHTML = '';
  order.forEach((id, idx) => {{
    const slot = document.createElement('span');
    slot.className = 'answer-slot';
    slot.innerHTML = `<b>${{idx + 1}}.</b> ID ${{id}} <button type="button" data-remove="${{id}}">×</button>`;
    selected.appendChild(slot);
  }});
  hidden.value = order.join(' ');
  chips.forEach(chip => chip.classList.toggle('used', order.includes(chip.dataset.id)));
}}
function addId(id) {{ if (!order.includes(id)) {{ order.push(id); renderOrder(); }} }}
function removeId(id) {{ order = order.filter(x => x !== id); renderOrder(); }}
chips.forEach(chip => chip.addEventListener('click', () => addId(chip.dataset.id)));
selected.addEventListener('click', (ev) => {{ const id = ev.target.dataset.remove; if (id) removeId(id); }});
document.getElementById('reset-order').addEventListener('click', () => {{ order = []; renderOrder(); }});
document.getElementById('use-solver-order').addEventListener('click', () => {{ order = solverOrder.filter(id => optionIds.includes(id)); renderOrder(); }});
order = initialOrder.filter(id => optionIds.includes(id));
renderOrder();
function normalizeText(v) {{ return (v || '').trim(); }}
function showToast(msg) {{
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 1600);
}}
function updateFieldState(field) {{
  const original = normalizeText(field.dataset.original);
  const checkbox = document.getElementById(field.dataset.check);
  const same = normalizeText(field.value) === original;
  if (checkbox) checkbox.checked = same;
  const box = field.closest('.card') || field.parentElement;
  if (box) box.classList.toggle('field-changed', !same);
}}
document.querySelectorAll('.watched-field').forEach((field) => {{
  field.addEventListener('input', () => updateFieldState(field));
  updateFieldState(field);
}});
document.querySelectorAll('.use-solver-text').forEach((btn) => {{
  btn.addEventListener('click', () => {{
    const target = document.querySelector(`[name="${{btn.dataset.target}}"]`);
    if (!target) {{ showToast('Field target tidak ketemu'); return; }}
    const before = target.value;
    target.value = btn.dataset.value || '';
    updateFieldState(target);
    target.focus();
    target.dispatchEvent(new Event('input', {{ bubbles: true }}));
    showToast(before === target.value ? 'Sudah sama dengan hasil solver' : 'Field diisi dari hasil solver');
  }});
}});
function setField(name, value) {{
  const target = document.querySelector(`[name="${{name}}"]`);
  if (!target) return;
  target.value = value || '';
  updateFieldState(target);
  target.dispatchEvent(new Event('input', {{ bubbles: true }}));
}}
function applyLatestSolver() {{
  if (!latestResult || !latestResult.success) {{ showToast('Latest solver belum ada atau gagal'); return; }}
  setField('question_text', latestResult.question_text || '');
  Object.entries(latestResult.options_text || {{}}).forEach(([id, text]) => setField(`option_${{id}}`, text || ''));
  order = (latestResult.submitted_answer_order || []).filter(id => optionIds.includes(String(id))).map(String);
  renderOrder();
  showToast('Latest solver result diterapkan ke field');
}}
const runLatestBtn = document.getElementById('run-latest-solver');
const applyLatestBtn = document.getElementById('apply-latest-solver');
const latestBox = document.getElementById('latest-solver-box');
if (runLatestBtn) {{
  runLatestBtn.addEventListener('click', async () => {{
    runLatestBtn.disabled = true;
    latestBox.textContent = 'Running latest solver...';
    try {{
      const res = await fetch(latestSolverUrl, {{ credentials: 'same-origin' }});
      latestResult = await res.json();
      const summary = {{
        success: latestResult.success,
        status: latestResult.status,
        confidence: latestResult.confidence,
        question_text: latestResult.question_text,
        options_text: latestResult.options_text,
        submitted_answer_order: latestResult.submitted_answer_order,
        error: latestResult.error_message || latestResult.error_code || null
      }};
      latestBox.textContent = JSON.stringify(summary, null, 2);
      applyLatestBtn.disabled = !latestResult.success;
      showToast(latestResult.success ? 'Latest solver selesai' : 'Latest solver gagal');
    }} catch (err) {{
      latestBox.textContent = 'Latest solver error: ' + err;
      showToast('Latest solver error');
    }} finally {{
      runLatestBtn.disabled = false;
    }}
  }});
}}
if (applyLatestBtn) applyLatestBtn.addEventListener('click', applyLatestSolver);
</script>
    """
    return html_page(case_id, body)


@app.post("/case/{case_id}/save")
async def save_case(case_id: str, request: Request) -> RedirectResponse:
    require_auth(request)
    path, data = load_case(case_id)
    form = await request.form()
    question_text = str(form.get("question_text") or "").strip()
    options_text = {}
    option_reviews = {}
    for opt in data["images"]["options"]:
        oid = str(opt["id"])
        options_text[oid] = str(form.get(f"option_{oid}") or "").strip()
        option_reviews[oid] = bool(form.get(f"option_correct_{oid}"))
    order = [x.strip() for x in str(form.get("correct_order") or "").replace(",", " ").split() if x.strip()]
    derived = auto_order(question_text, options_text, int(data["option_count"]))
    if not order and derived:
        order = derived
    data["status"] = "labeled"
    data["solver_review"] = {
        "question_read_correct": bool(form.get("question_correct")),
        "option_reads_correct": option_reviews,
        "submitted_order_correct": bool(form.get("submitted_order_correct")),
    }
    data["manual_label"] = {
        "question_text": question_text,
        "question_tokens": split_tokens(question_text, int(data["option_count"])),
        "options_text": options_text,
        "correct_answer_order": order,
        "auto_derived_order": derived,
        "notes": str(form.get("notes") or "").strip(),
    }
    labeled = LABEL_ROOT / "labeled" / path.name
    labeled.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    path.unlink()
    return RedirectResponse(f"/labeled/{case_id}?{token_q(request)}", status_code=303)


@app.get("/jobs/status")
def jobs_status(request: Request) -> dict[str, Any]:
    require_auth(request)
    return current_job_status()


@app.post("/jobs/start-eval")
def jobs_start_eval(
    request: Request,
    include_accepted: str = Form("1"),
    include_labeled: str = Form("1"),
    accepted_limit: str = Form(""),
    workers: int = Form(2),
    eval_mode: str = Form("stored-debug"),
) -> RedirectResponse:
    require_auth(request)
    global JOB_THREAD
    with JOB_LOCK:
        status = current_job_status()
        if status.get("status") == "running" and JOB_THREAD and JOB_THREAD.is_alive():
            return RedirectResponse(f"/stats?{token_q(request)}", status_code=303)
        limit = int(accepted_limit) if str(accepted_limit).strip() else None
        job_id = f"eval-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        JOB_STOP_PATH.unlink(missing_ok=True)
        write_job_status({
            "job_id": job_id,
            "status": "running",
            "kind": "stable_eval",
            "progress": 0,
            "message": "Starting background eval job...",
            "can_stop": True,
        })
        JOB_THREAD = threading.Thread(
            target=run_eval_job,
            kwargs={
                "job_id": job_id,
                "include_accepted": include_accepted == "1",
                "include_labeled": include_labeled == "1",
                "accepted_limit": limit,
                "workers": workers,
                "eval_mode": eval_mode,
            },
            daemon=True,
        )
        JOB_THREAD.start()
    return RedirectResponse(f"/stats?{token_q(request)}", status_code=303)


@app.post("/jobs/stop")
def jobs_stop(request: Request) -> RedirectResponse:
    require_auth(request)
    ensure_dirs()
    JOB_STOP_PATH.write_text(str(time.time()))
    status = current_job_status()
    status["message"] = "Stop requested. Waiting current case to finish..."
    status["can_stop"] = False
    write_job_status(status)
    return RedirectResponse(f"/stats?{token_q(request)}", status_code=303)


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request) -> str:
    require_auth(request)
    q = token_q(request)
    live = solver_stats_data()
    labels = label_eval_data()
    job = job_status_data()
    progress = max(0, min(100, int(job.get("progress") or 0)))

    def stat_card(name: str, val: Any, cls: str = "") -> str:
        return f"<div class='stat {cls}'><span>{escape(name)}</span><br><b>{escape(str(val))}</b></div>"

    def group(title: str, d: dict[str, Any]) -> str:
        return f"""<div class='card'><h2>{escape(title)}</h2><div class='grid'>
        {stat_card('Total', d['total'])}{stat_card('Berhasil', d['accepted'], 'good')}{stat_card('Gagal', d['rejected'], 'bad')}{stat_card('Error', d['errors'], 'warn')}{stat_card('Success rate', str(d['success_rate']) + '%', 'good')}
        </div></div>"""

    body = f"""
    <div class='top'><div><h1>Solver performance center</h1><div class='tag'>live ClaimCoin attempts + labeled dataset evaluation</div></div><a class='btn btn2' href='/?{q}'>Back</a></div>
    {group('Overall raw live attempts', live['overall'])}
    {group('Recent live attempts, last 100', live['last_100'])}
    {group('Post tuning window, attempt >= 1013', live['post_tuning_1013'])}
    <div class='card'><h2>Label-based solver check</h2><div class='help'>Ini ngecek label yang sudah Boskuu save. Kalau solver order sama dengan correct order label, dihitung exact. Kalau belum ada label cukup banyak, angka ini belum final.</div><div class='grid'>
      {stat_card('Labeled total', labels['total'])}{stat_card('Checked', labels['checked'])}{stat_card('Solver exact', labels['solver_exact'], 'good')}{stat_card('Corrected by human', labels['corrected'], 'bad')}{stat_card('Label exact rate', str(labels['label_success_rate']) + '%', 'good')}
    </div></div>
    <div class='card'><h2>Retuning / testing job</h2><div class='help'>Fondasi job progress sudah ada. Tombol start retuning/testing akan disambung ke runner background berikutnya, jadi kalau web ditutup status tetap bisa dibaca lagi dari sini.</div>
      <div class='grid'>{stat_card('Status', job.get('status'))}{stat_card('Mode', job.get('eval_mode') or '-')}{stat_card('Progress', str(progress) + '%')}{stat_card('Done / Total', str(job.get('done', 0)) + ' / ' + str(job.get('total', 0)))}{stat_card('Running', job.get('running', 0))}{stat_card('OK', job.get('ok', 0), 'good')}{stat_card('Wrong', job.get('wrong', 0), 'bad')}{stat_card('Errors', job.get('errors', 0), 'warn')}{stat_card('Live success', str(job.get('success_rate', 0)) + '%', 'good')}</div>
      <div class='progress'><span style='width:{progress}%'></span></div>
      <form method='post' action='/jobs/start-eval?{q}'><input type='hidden' name='include_accepted' value='1'><input type='hidden' name='include_labeled' value='1'><label>Accepted raw limit, kosong = semua accepted selain yang sudah dilabel</label><input name='accepted_limit' value=''><label>Eval mode</label><select name='eval_mode'><option value='stored-debug' selected>Fast matcher replay from stored OCR cache/debug</option><option value='current-ocr'>Slow rerun current OCR</option></select><label>Workers, default 2, max 3</label><select name='workers'><option value='2' selected>2 workers, recommended for fast mode</option><option value='1'>1 worker</option><option value='3'>3 workers, heavier</option></select><p><button>Start full eval: accepted success raw + labels</button></p></form>
      <form method='post' action='/jobs/stop?{q}'><p><button class='danger' {'disabled' if not job.get('can_stop') else ''}>Stop current job</button></p></form>
      <details><summary>Failure sample / raw status JSON</summary><pre id='job-json'>{escape(json.dumps(job, ensure_ascii=False, indent=2))}</pre></details>
    </div>
<script>
async function refreshJob() {{
  try {{
    const res = await fetch('/jobs/status?{q}', {{ credentials: 'same-origin' }});
    const job = await res.json();
    const box = document.getElementById('job-json');
    if (box) box.textContent = JSON.stringify(job, null, 2);
    if (job.status === 'running') setTimeout(() => location.reload(), 7000);
  }} catch (e) {{}}
}}
refreshJob();
</script>
    """
    return html_page("Solver stats", body)


@app.get("/gallery", response_class=HTMLResponse)
def gallery(request: Request) -> str:
    require_auth(request)
    q = token_q(request)
    cards = []
    for path in queue_files()[:100]:
        data = json.loads(path.read_text())
        qrel = data["images"]["question"].replace("images/", "")
        cards.append(f"<div class='card'><h3>{data['case_id']}</h3><img src='/images/{qrel}?{q}'><p><a class='btn btn2' href='/case/{data['case_id']}?{q}'>Open</a></p></div>")
    return html_page("Gallery", f"<div class='top'><h1>Queue Gallery</h1><a class='btn btn2' href='/?{q}'>Back</a></div><div class='case-list'>{''.join(cards)}</div>")


@app.get("/labeled", response_class=HTMLResponse)
def labeled_list(request: Request) -> str:
    require_auth(request)
    q = token_q(request)
    cards = []
    for path in labeled_files()[:120]:
        data = json.loads(path.read_text())
        label = data.get("manual_label") or {}
        order = " ".join(label.get("correct_answer_order") or [])
        cards.append(f"""<div class='card'><b>{data['case_id']}</b><div class='small'>attempt {data['attempt_id']} • {data['verdict']}</div>
        <div class='small'>question: {escape(label.get('question_text',''))}</div><div class='small'>order: {escape(order)}</div>
        <p><a class='btn btn2' href='/labeled/{data['case_id']}?{q}'>Review</a></p></div>""")
    body = f"<div class='top'><div><h1>Review labeled cases</h1><div class='tag'>latest saved labels first</div></div><a class='btn btn2' href='/?{q}'>Back</a></div><div class='case-list'>{''.join(cards) or '<div class=card>No labeled cases yet.</div>'}</div>"
    return html_page("Review labeled", body)


@app.get("/labeled/{case_id}", response_class=HTMLResponse)
def labeled_detail(case_id: str, request: Request) -> str:
    require_auth(request)
    q = token_q(request)
    _, data = load_labeled(case_id)
    label = data.get("manual_label") or {}
    review = data.get("solver_review") or {}
    opts = []
    for opt in data["images"]["options"]:
        oid = str(opt["id"])
        opts.append(f"""<div class='option'><div><img src='{image_url(opt['image'], q)}'><div class='pill'>ID {oid}</div></div>
        <div><label>Final text</label><input readonly value='{escape((label.get('options_text') or {}).get(oid, ''))}'>
        <div class='small'>solver read correct: {escape(str((review.get('option_reads_correct') or {}).get(oid)))}</div></div></div>""")
    qrel = image_url(data["images"]["question"], q)
    order = " ".join(label.get("correct_answer_order") or [])
    body = f"""
    <div class='top'><div><h1>{data['case_id']} review</h1><div class='tag'>saved label result</div></div><div><a class='btn' href='/labeled/{case_id}/edit?{q}'>Edit label</a> <a class='btn btn2' href='/labeled?{q}'>All labels</a> <a class='btn btn2' href='/?{q}'>Home</a></div></div>
    <div class='card'><h2>Question</h2><img src='{qrel}'><label>Final question text</label><input readonly value='{escape(label.get('question_text',''))}'><div class='small'>tokens: {escape(', '.join(label.get('question_tokens') or []))}</div><div class='small'>solver question correct: {escape(str(review.get('question_read_correct')))}</div></div>
    <div class='card'><h2>Options</h2>{''.join(opts)}</div>
    <div class='card'><h2>Final order</h2><div class='stat'><b>{escape(order)}</b></div><div class='small'>auto-derived: {escape(' '.join(label.get('auto_derived_order') or []))}</div><div class='small'>submitted order was correct: {escape(str(review.get('submitted_order_correct')))}</div><label>Notes</label><textarea readonly rows='3'>{escape(label.get('notes',''))}</textarea></div>
    """
    return html_page(f"{case_id} review", body)


@app.get("/labeled/{case_id}/edit", response_class=HTMLResponse)
def labeled_edit(case_id: str, request: Request) -> str:
    require_auth(request)
    q = token_q(request)
    _, data = load_labeled(case_id)
    label = data.get("manual_label") or {}
    current = data.get("current_solver") or {}
    option_ids = [str(opt["id"]) for opt in data["images"]["options"]]
    question_rel = image_url(data["images"]["question"], q)
    question_value = label.get("question_text") or current.get("question_text") or ""
    opts = []
    for opt in data["images"]["options"]:
        oid = str(opt["id"])
        final_text = (label.get("options_text") or {}).get(oid) or (current.get("options_text") or {}).get(oid, "")
        opts.append(f"""<div class='option'><div><img src='{image_url(opt['image'], q)}'><div class='pill'>ID {oid}</div></div>
        <div><label>Final option text</label><input name='option_{oid}' value='{escape(final_text)}'></div></div>""")
    order_value = " ".join(label.get("correct_answer_order") or [])
    option_buttons = "".join([f"<button type='button' class='order-chip' data-id='{escape(oid)}'>ID {escape(oid)}</button>" for oid in option_ids])
    body = f"""
    <div class='top'><div><h1>Edit {data['case_id']}</h1><div class='tag'>edit saved label, raw capture stays preserved</div></div><a class='btn btn2' href='/labeled/{case_id}?{q}'>Cancel</a></div>
    <form method='post' action='/labeled/{case_id}/edit?{q}'>
      <div class='card'><h2>Question</h2><img src='{question_rel}'><label>Final question text</label><input name='question_text' value='{escape(question_value)}'></div>
      <div class='card'><h2>Options</h2>{''.join(opts)}</div>
      <div class='card'><h2>Final answer order</h2><div class='order-board'><div><label>Available option IDs</label><div id='available-options' class='chipbox'>{option_buttons}</div></div><div><label>Your selected order</label><div id='selected-order' class='chipbox'></div></div></div>
      <input type='hidden' id='correct_order' name='correct_order' value='{escape(order_value)}'>
      <p><button type='button' class='btn btn2' id='reset-order'>Reset order</button></p>
      <label>Notes</label><textarea name='notes' rows='3'>{escape(label.get('notes',''))}</textarea>
      <p><button>Save edited label</button></p></div>
    </form>
<script>
const optionIds = {json.dumps(option_ids)};
const initialOrder = {json.dumps(order_value.split())};
const hidden = document.getElementById('correct_order');
const selected = document.getElementById('selected-order');
const chips = Array.from(document.querySelectorAll('.order-chip'));
let order = [];
function renderOrder() {{
  selected.innerHTML = '';
  order.forEach((id, idx) => {{
    const slot = document.createElement('span');
    slot.className = 'answer-slot';
    slot.innerHTML = `<b>${{idx + 1}}.</b> ID ${{id}} <button type="button" data-remove="${{id}}">×</button>`;
    selected.appendChild(slot);
  }});
  hidden.value = order.join(' ');
  chips.forEach(chip => chip.classList.toggle('used', order.includes(chip.dataset.id)));
}}
function addId(id) {{ if (!order.includes(id)) {{ order.push(id); renderOrder(); }} }}
function removeId(id) {{ order = order.filter(x => x !== id); renderOrder(); }}
chips.forEach(chip => chip.addEventListener('click', () => addId(chip.dataset.id)));
selected.addEventListener('click', (ev) => {{ const id = ev.target.dataset.remove; if (id) removeId(id); }});
document.getElementById('reset-order').addEventListener('click', () => {{ order = []; renderOrder(); }});
order = initialOrder.filter(id => optionIds.includes(id));
renderOrder();
</script>
    """
    return html_page(f"Edit {case_id}", body)


@app.post("/labeled/{case_id}/edit")
async def labeled_edit_save(case_id: str, request: Request) -> RedirectResponse:
    require_auth(request)
    path, data = load_labeled(case_id)
    form = await request.form()
    question_text = str(form.get("question_text") or "").strip()
    options_text = {}
    for opt in data["images"]["options"]:
        oid = str(opt["id"])
        options_text[oid] = str(form.get(f"option_{oid}") or "").strip()
    order = [x.strip() for x in str(form.get("correct_order") or "").replace(",", " ").split() if x.strip()]
    data["manual_label"] = {
        **(data.get("manual_label") or {}),
        "question_text": question_text,
        "question_tokens": split_tokens(question_text, int(data["option_count"])),
        "options_text": options_text,
        "correct_answer_order": order,
        "auto_derived_order": auto_order(question_text, options_text, int(data["option_count"])),
        "notes": str(form.get("notes") or "").strip(),
    }
    data["status"] = "labeled"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return RedirectResponse(f"/labeled/{case_id}?{token_q(request)}", status_code=303)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    ensure_dirs()
    token = get_token()
    print(f"Label Studio token: {token}")
    print(f"Local URL: http://{args.host}:{args.port}/?token=***")
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
