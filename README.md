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

`fast` reduces preprocessing variants and Tesseract pass count so the caller can submit sooner on sites with tight anti-bot/session windows.

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
    "debug": true
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

## Project layout

```text
src/antibot_image_solver/
  api/                 FastAPI app and schemas
  adapters/            Site-specific parser adapters
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
