#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import secrets
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from label_claimcoin_antibot import (  # noqa: E402
    DEFAULT_CLAIMCOIN_ROOT,
    DEFAULT_LABEL_ROOT,
    auto_order,
    build_queue_case,
    split_tokens,
)

CLAIMCOIN_ROOT = DEFAULT_CLAIMCOIN_ROOT
LABEL_ROOT = DEFAULT_LABEL_ROOT
TOKEN_PATH = LABEL_ROOT / "web_auth_token.txt"

app = FastAPI(title="ClaimCoin AntiBot Label Studio")


def ensure_dirs() -> None:
    for sub in ["queue", "labeled", "skipped", "images", "preview", "web"]:
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
a{{color:var(--accent)}} .wrap{{max-width:1220px;margin:0 auto;padding:24px}} .top{{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:20px}}
h1{{font-size:28px;margin:0;letter-spacing:-.04em}} .tag{{color:var(--muted);font-size:13px}}
.card{{background:linear-gradient(180deg,var(--panel),#101511);border:1px solid var(--line);border-radius:18px;padding:18px;margin:14px 0;box-shadow:0 18px 60px #0008}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}} .stat{{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:14px}}
.stat b{{font-size:28px;color:var(--accent)}} button,.btn{{background:var(--accent);color:#071008;border:0;border-radius:12px;padding:10px 14px;font-weight:800;cursor:pointer;text-decoration:none;display:inline-block}}
.btn2{{background:#233027;color:var(--ink);border:1px solid var(--line)}} .danger{{background:var(--bad);color:#200}}
input,textarea,select{{width:100%;background:#0b100d;color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit}}
label{{display:block;color:var(--muted);font-size:12px;margin:9px 0 5px}} img{{max-width:100%;background:white;border-radius:10px;border:1px solid #334}}
.case-list{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}} .pill{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;color:var(--muted);font-size:12px}}
.option{{display:grid;grid-template-columns:210px 1fr;gap:14px;align-items:start;border-top:1px solid var(--line);padding-top:14px;margin-top:14px}}
pre{{white-space:pre-wrap;color:#cfe6d2;background:#09100c;border:1px solid var(--line);padding:10px;border-radius:10px;max-height:170px;overflow:auto}}
.small{{font-size:12px;color:var(--muted)}} .ok{{color:var(--good)}} .bad{{color:var(--bad)}}
</style></head><body><div class="wrap">{body}</div></body></html>"""


def queue_files() -> list[Path]:
    ensure_dirs()
    return sorted((LABEL_ROOT / "queue").glob("*.json"))


def load_case(case_id: str) -> tuple[Path, dict[str, Any]]:
    path = LABEL_ROOT / "queue" / f"{case_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="case not found in queue")
    return path, json.loads(path.read_text())


def stats_data() -> dict[str, Any]:
    ensure_dirs()
    con = sqlite3.connect(CLAIMCOIN_ROOT / "state" / "claimcoin.sqlite3")
    total = con.execute("select count(*) from antibot_attempts").fetchone()[0]
    accepted = con.execute("select count(*) from antibot_attempts where verdict='accepted_success'").fetchone()[0]
    rejected = con.execute("select count(*) from antibot_attempts where verdict='server_reject_antibot'").fetchone()[0]
    return {
        "queue": len(list((LABEL_ROOT / "queue").glob("*.json"))),
        "labeled": len(list((LABEL_ROOT / "labeled").glob("*.json"))),
        "skipped": len(list((LABEL_ROOT / "skipped").glob("*.json"))),
        "raw_total": total,
        "raw_accepted": accepted,
        "raw_rejected": rejected,
    }


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
        <div class='small'>solver: {data['current_solver'].get('question_text','')}</div>
        <p><a class='btn btn2' href='/case/{data['case_id']}?{q}'>Label case</a></p></div>""")
    body = f"""
    <div class='top'><div><h1>ClaimCoin AntiBot Label Studio</h1><div class='tag'>private tunnel UI • raw captures preserved</div></div><a class='btn btn2' href='/gallery?{q}'>Gallery</a></div>
    <div class='grid'>
      <div class='stat'><span>Queue</span><br><b>{st['queue']}</b></div><div class='stat'><span>Labeled</span><br><b>{st['labeled']}</b></div><div class='stat'><span>Raw rejected</span><br><b>{st['raw_rejected']}</b></div><div class='stat'><span>Raw total</span><br><b>{st['raw_total']}</b></div>
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


@app.get("/case/{case_id}", response_class=HTMLResponse)
def case_page(case_id: str, request: Request) -> str:
    require_auth(request)
    q = token_q(request)
    _, data = load_case(case_id)
    current = data["current_solver"]
    ml = data.get("manual_label") or {}
    question_value = ml.get("question_text") or current.get("question_text") or ""
    opts_html = []
    for opt in data["images"]["options"]:
        oid = str(opt["id"])
        rel = opt["image"].replace("images/", "")
        solver_text = current.get("options_text", {}).get(oid, "")
        value = (ml.get("options_text") or {}).get(oid) or solver_text
        raw = current.get("tesseract_option_ocr", {}).get(oid, [])
        opts_html.append(f"""<div class='option'><div><img src='/images/{rel}?{q}'><div class='pill'>ID {oid}</div></div><div>
        <label>Option {oid} text</label><input name='option_{oid}' value='{escape(value)}'>
        <label><input type='checkbox' name='option_correct_{oid}' value='1' checked style='width:auto'> solver read correct</label>
        <pre>{escape(json.dumps(raw, ensure_ascii=False, indent=2))}</pre></div></div>""")
    order_value = " ".join(ml.get("correct_answer_order") or current.get("submitted_answer_order") or [])
    question_rel = data["images"]["question"].replace("images/", "")
    body = f"""
    <div class='top'><div><h1>{data['case_id']}</h1><div class='tag'>attempt {data['attempt_id']} • {data['verdict']} • confidence {current.get('confidence')}</div></div><a class='btn btn2' href='/?{q}'>Back</a></div>
    <form method='post' action='/case/{case_id}/save?{q}'>
    <div class='card'><h2>Question</h2><img src='/images/{question_rel}?{q}'><label>Question text</label><input name='question_text' value='{escape(question_value)}'>
    <label><input type='checkbox' name='question_correct' value='1' checked style='width:auto'> solver question read correct</label>
    <pre>{escape(json.dumps(current.get('tesseract_question_ocr', []), ensure_ascii=False, indent=2))}</pre></div>
    <div class='card'><h2>Options</h2>{''.join(opts_html)}</div>
    <div class='card'><h2>Final order</h2><div class='small'>Solver submitted: {' '.join(current.get('submitted_answer_order', []))}</div>
    <label>Correct answer order</label><input name='correct_order' value='{escape(order_value)}'>
    <label><input type='checkbox' name='submitted_order_correct' value='1' style='width:auto'> submitted order already correct</label>
    <label>Notes</label><textarea name='notes' rows='3'>{escape(ml.get('notes',''))}</textarea>
    <p><button>Save as labeled</button> <a class='btn btn2' href='/?{q}'>Skip, keep in queue</a></p></div></form>
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
    return RedirectResponse(f"/?{token_q(request)}", status_code=303)


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    ensure_dirs()
    token = get_token()
    print(f"Label Studio token: {token}")
    print(f"Local URL: http://{args.host}:{args.port}/?token={token}")
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
