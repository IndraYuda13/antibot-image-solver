# antibot-image-solver

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![OCR](https://img.shields.io/badge/OCR-Tesseract-5C2D91)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Scope](https://img.shields.io/badge/scope-closed--set%20antibot-blue)

Standalone OCR + semantic matcher for anti-bot image ordering challenges.

This project extracts the reusable solver core from the EarnCryptoWRS anti-bot work into a separate package. It focuses on the image-to-order problem, not full browser automation.

## What it does

- OCR instruction images across multiple preprocessing variants
- Normalize noisy OCR into canonical semantic forms
- Match closed-set anti-bot families such as:
  - numbers
  - arithmetic expressions
  - number words
  - roman or symbolic numerals
  - small animal vocabularies
- Return ordered labels or ordered option ids
- Expose both a CLI and a FastAPI service

## What it does not do

- Login to target sites
- Manage cookies or sessions
- Refresh site-specific telemetry like `smart_token`
- Click browser DOM elements by itself
- Guarantee end-to-end claim success on faucet sites

## System requirement

This project expects a working `tesseract` binary on the host.

Example install on Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

## Install

```bash
cd projects/antibot-image-solver
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
```

## OCR speed profiles

By default the OCR pipeline uses the `full` profile for maximum recall. For short-lived live challenges where speed matters more than extra OCR passes, set:

```bash
export ANTIBOT_OCR_PROFILE=fast
```

`fast` now uses a two-stage path for option-image challenges: first it tries a `turbo` OCR pass and accepts only high-confidence matches, then falls back to the fuller fast pass when confidence is lower. This keeps easy ClaimCoin-style cases quick without trusting weak low-confidence OCR.

Tesseract subprocesses are capped by `ANTIBOT_OCR_TIMEOUT_SECONDS`, default `3.0`, so one slow OCR pass cannot hang an entire claim indefinitely.

Optional browser tools:

```bash
pip install -e .[browser]
```

Dev/test extras:

```bash
pip install -e .[dev]
```

## CLI quickstart

Analyze one instruction image:

```bash
antibot-image-solver analyze-image \
  --image ./samples/instruction.png \
  --json
```

Solve from an instruction image plus text candidates:

```bash
antibot-image-solver solve-image \
  --image ./samples/instruction.png \
  --candidates dog,cat,mouse \
  --json
```

Capture a labeled benchmark record while solving:

```bash
antibot-image-solver solve-image \
  --image ./samples/instruction.png \
  --candidates dog,cat,mouse \
  --capture-dir ./captures/claimcoin \
  --capture-verdict success \
  --capture-tags claimcoin,live \
  --capture-challenge-id claimcoin-20260416-001 \
  --json
```

Solve from an instruction image plus option images:

```bash
antibot-image-solver solve-options \
  --instruction-image ./samples/instruction.png \
  --option dog=./samples/dog.png \
  --option cat=./samples/cat.png \
  --option mouse=./samples/mouse.png \
  --json
```

Run the API:

```bash
antibot-image-solver-api --host 127.0.0.1 --port 8010
```

## API quickstart

### Health

```bash
curl -s http://127.0.0.1:8010/health
```

### Solve using text candidates

```bash
curl -s http://127.0.0.1:8010/solve/antibot-image \
  -H 'content-type: application/json' \
  -d '{
    "instruction_image_base64": "...",
    "candidates": ["dog", "cat", "mouse"],
    "domain_hint": "earncryptowrs",
    "debug": true,
    "capture": {
      "output_dir": "./captures/claimcoin",
      "verdict": "uncertain",
      "tags": ["claimcoin", "api"]
    }
  }'
```

### Solve using option images

```bash
curl -s http://127.0.0.1:8010/solve/antibot-image \
  -H 'content-type: application/json' \
  -d '{
    "instruction_image_base64": "...",
    "options": [
      {"id": "6940", "image_base64": "..."},
      {"id": "6138", "image_base64": "..."},
      {"id": "4910", "image_base64": "..."}
    ],
    "domain_hint": "earncryptowrs",
    "debug": true
  }'
```

## Durable capture workflow

When `capture` is enabled from CLI or API, the solver writes:

- `CAPTURE_DIR/index.jsonl`, append-only benchmark index
- `CAPTURE_DIR/<challenge_id>/record.json`, full challenge input + solver output/debug payload

Each `record.json` contains:

- raw instruction image base64
- raw option image base64 values when option-image mode is used
- text candidates
- solver result payload
- solver internals when debug or capture is enabled
- a caller-supplied verdict label: `success`, `reject_antibot`, `reject_captcha_or_session`, or `uncertain`

This is meant for replay, offline evaluation, and postmortem analysis when Boskuu's ClaimCoin flow rejects a solve even though the OCR looked plausible.

## ClaimCoin integration sketch

ClaimCoin can call the local API after it has already collected the challenge images in browser automation:

1. POST `instruction_image_base64` plus either `candidates` or `options[].image_base64`.
2. Set `request_id` to the ClaimCoin job/challenge id.
3. Include `capture.output_dir` and a provisional verdict like `uncertain`.
4. After submit, rewrite or recapture the final label from ClaimCoin's observed outcome:
   - `success` when claim passes
   - `reject_antibot` when the antibot checker rejects the order
   - `reject_captcha_or_session` when upstream captcha/session state failed first
   - `uncertain` when the outcome is still ambiguous

Minimal API payload shape for ClaimCoin:

```json
{
  "request_id": "claimcoin-job-123",
  "instruction_image_base64": "...",
  "candidates": ["dog", "cat", "mouse"],
  "domain_hint": "claimcoin",
  "capture": {
    "output_dir": "./captures/claimcoin",
    "verdict": "uncertain",
    "tags": ["claimcoin", "prod"]
  }
}
```

The response includes `capture.record_path`, so ClaimCoin can correlate the browser outcome with the stored benchmark artifact.

## Project layout

```text
src/antibot_image_solver/
  api/                 FastAPI app and schemas
  adapters/            Site-specific parser adapters
  capture.py           Persistent capture/index writer for benchmarking
  cli.py               CLI entrypoint
  matcher.py           Permutation scoring and order solving
  models.py            Shared dataclasses
  normalize.py         Canonicalization helpers
  ocr.py               Tesseract OCR pipeline
  solver.py            High-level solve functions
```

## Public-safe packaging note

This repo is intended to keep the reusable solver core separate from live site operations.

Do not mix in:
- live faucet credentials
- hardcoded email defaults
- local artifact directories from operational systems
- live screenshots or session state

## Current status

`v0.1.0` goal:
- reusable solver core
- CLI
- FastAPI endpoint
- sanitized EarnCryptoWRS HTML adapter
- deterministic matcher tests

## License

See `LICENSE-STATUS.md`.
