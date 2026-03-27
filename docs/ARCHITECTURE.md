# Architecture

## Goal

`antibot-image-solver` is a standalone OCR and semantic matching service for anti-bot ordering puzzles.

It is intentionally narrower than a full browser automation bot.

## Layers

### 1. Core solver

Located under `src/antibot_image_solver/`.

Main modules:
- `models.py`
- `ocr.py`
- `normalize.py`
- `matcher.py`
- `solver.py`

Responsibilities:
- preprocess instruction or option images
- run OCR through Tesseract
- normalize noisy OCR into canonical forms
- score permutations of candidate options
- return ordered ids, ordered labels, confidence, and debug metadata

### 2. Adapter layer

Located under `src/antibot_image_solver/adapters/`.

Current adapter:
- `earncryptowrs.py`

Responsibilities:
- parse target-site HTML
- extract instruction image and option images
- convert site-specific form structure into the generic challenge model

### 3. API layer

Located under `src/antibot_image_solver/api/`.

Responsibilities:
- validate request payloads
- expose `/health`, `/analyze/antibot-image`, and `/solve/antibot-image`
- serialize `SolveResult` into a stable JSON response

### 4. CLI layer

Located in `cli.py`.

Responsibilities:
- local image analysis
- local solving with text candidates or option images
- running the FastAPI service

## Why this split matters

The solver is reusable only if site behavior stays outside the core.

Keep these concerns out of the core package:
- login flow
- cookies or sessions
- browser DOM clicking
- telemetry refresh such as site-specific `smart_token`
- business-rule verification such as dashboard counter deltas
- runtime lock memory tied to a single faucet site

## Current target challenge families

The MVP is optimized for the closed-set families observed in EarnCryptoWRS-style puzzles:
- digits and short numeric tokens
- arithmetic expressions
- number words
- roman or symbolic numeral variants
- small recurring animal vocabularies

## Integration pattern

A target automation project should:
1. fetch or capture the challenge form
2. build the generic challenge payload
3. call the solver library or HTTP API
4. receive ordered ids or labels
5. perform its own browser click or submit logic separately

## Public-safe packaging rule

This project is safe to publish because it keeps reusable solving logic separate from:
- live credentials
- live browser profiles
- workspace-specific artifact paths
- target-site operational state
