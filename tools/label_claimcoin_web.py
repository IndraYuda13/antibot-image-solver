#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from html import escape
import secrets
import sqlite3
import time
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

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
JOB_STATUS_PATH = LABEL_ROOT / "jobs" / "solver_eval_status.json"

app = FastAPI(title="ClaimCoin AntiBot Label Studio")


def ensure_dirs() -> None:
    for sub in ["queue", "labeled", "skipped", "images", "preview", "web", "jobs"]:
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
        "post_tuning_547": verdict_stats("id >= ?", (547,)),
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
    if JOB_STATUS_PATH.exists():
        return json.loads(JOB_STATUS_PATH.read_text())
    return {"status": "idle", "kind": None, "progress": 0, "message": "Belum ada job retuning/testing aktif.", "updated_at": None}


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
    {group('Post tuning window, attempt >= 547', live['post_tuning_547'])}
    <div class='card'><h2>Label-based solver check</h2><div class='help'>Ini ngecek label yang sudah Boskuu save. Kalau solver order sama dengan correct order label, dihitung exact. Kalau belum ada label cukup banyak, angka ini belum final.</div><div class='grid'>
      {stat_card('Labeled total', labels['total'])}{stat_card('Checked', labels['checked'])}{stat_card('Solver exact', labels['solver_exact'], 'good')}{stat_card('Corrected by human', labels['corrected'], 'bad')}{stat_card('Label exact rate', str(labels['label_success_rate']) + '%', 'good')}
    </div></div>
    <div class='card'><h2>Retuning / testing job</h2><div class='help'>Fondasi job progress sudah ada. Tombol start retuning/testing akan disambung ke runner background berikutnya, jadi kalau web ditutup status tetap bisa dibaca lagi dari sini.</div>
      <div class='grid'>{stat_card('Status', job.get('status'))}{stat_card('Kind', job.get('kind') or '-')}{stat_card('Progress', str(progress) + '%')}{stat_card('Message', job.get('message') or '-')}</div>
      <div class='progress'><span style='width:{progress}%'></span></div>
      <p><button class='btn btn2' disabled>Start label test, incoming</button> <button class='btn btn2' disabled>Start retune, incoming</button></p>
    </div>
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
    <div class='top'><div><h1>{data['case_id']} review</h1><div class='tag'>saved label result</div></div><div><a class='btn btn2' href='/labeled?{q}'>All labels</a> <a class='btn btn2' href='/?{q}'>Home</a></div></div>
    <div class='card'><h2>Question</h2><img src='{qrel}'><label>Final question text</label><input readonly value='{escape(label.get('question_text',''))}'><div class='small'>tokens: {escape(', '.join(label.get('question_tokens') or []))}</div><div class='small'>solver question correct: {escape(str(review.get('question_read_correct')))}</div></div>
    <div class='card'><h2>Options</h2>{''.join(opts)}</div>
    <div class='card'><h2>Final order</h2><div class='stat'><b>{escape(order)}</b></div><div class='small'>auto-derived: {escape(' '.join(label.get('auto_derived_order') or []))}</div><div class='small'>submitted order was correct: {escape(str(review.get('submitted_order_correct')))}</div><label>Notes</label><textarea readonly rows='3'>{escape(label.get('notes',''))}</textarea></div>
    """
    return html_page(f"{case_id} review", body)


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
