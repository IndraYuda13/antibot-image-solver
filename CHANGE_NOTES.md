# Change Notes

## 2026-04-29 - ClaimCoin low-confidence full OCR fallback

- Trigger evidence:
  - After matcher patch `e3e8a97`, live post-patch attempts reached `22/23` accepted (`95.65%`) with new reject id `500` at confidence `0.3499`.
  - Target was raised to `98%++`; low-confidence samples are the best next lever because confident cases are already passing and broad mappings risk overfitting.
- Files touched:
  - `src/antibot_image_solver/solver.py`
  - `tests/test_solver_hybrid.py`
  - `tools/evaluate_claimcoin_history.py`
  - `docs/superpowers/plans/2026-04-29-claimcoin-low-confidence-fallback.md`
- What changed:
  - Added configurable low-confidence fallback knobs:
    - `ANTIBOT_LOW_CONFIDENCE_THRESHOLD`, default `0.50`
    - `ANTIBOT_FULL_FALLBACK_MIN_GAIN`, default `0.08`
  - In fast option-image mode, solver now still runs turbo first, then fast, and runs one full OCR fallback only when the fast result is below threshold.
  - Full fallback is accepted only when it improves confidence by at least the configured minimum gain; otherwise the fast result is kept with audit metadata showing the fallback was tried and not improved.
  - Added the historical evaluator script used for `shrtlnksolver` screen progress and offline regression checks.
- Verification:
  - `tests/test_solver_hybrid.py`: 6 passed.
  - Full test suite: 28 passed.
  - Live reject id `500` replay exercised the fallback path; full OCR did not improve confidence on that sample, so the solver correctly kept the fast result and recorded `fallback_reason=low_confidence_not_improved`.
- Do not casually remove:
  - The min-gain gate. Accepting any full OCR result just because it ran can swap one low-confidence guess for another and hurt accepted samples.
  - The fallback metadata. It is needed to identify whether future live successes/rejects came from turbo, fast, or full fallback.

## 2026-04-29 - ClaimCoin reject-sample matcher correction stage 2

- Trigger evidence:
  - ClaimCoin run-loop passed the requested +20-claim checkpoint. Latest DB state reached attempt `474`.
  - Latest 20 attempts after id `454`: 15 accepted, 5 `Invalid Anti-Bot Links`, success rate `75%`.
  - The newest rejected captures showed wrong ordering on distorted random-text tokens, especially `pnk/org/blk` and `OK/|UV/yay` style samples.
- Files touched:
  - `src/antibot_image_solver/matcher.py`
  - `src/antibot_image_solver/normalize.py`
  - `tests/test_matcher.py`
- What changed:
  - Added a scoring guard so numeric aliases like `0/zero/1/one` do not dominate alphabetic random-token matches unless the instruction token itself is numeric or number-word-like.
  - Added narrow ClaimCoin OCR confusion mappings for live rejected samples: `pnk->pin`, `blk/ik->bk`, `uv/iuv/luv->ww`, `ouy/quy->yy`, `aor->got`, `pan/pon->pen`, plus accepted-sample guards `top->op`, `aip/aup->cvp`.
  - Added regression tests for two rejected sample classes and one accepted sample that must not regress.
- Verification:
  - `tests/test_matcher.py`: 8 passed.
  - Full test suite: 23 passed.
  - Stored-debug replay on latest 30 accepted ClaimCoin captures: 0 mismatches.
  - Stored-debug replay on latest rejected captures corrected attempts `465` and `474`; attempts `467`, `469`, and `473` still need more evidence/visual calibration before broader changes.
- Do not casually remove:
  - The numeric-alias guard. It prevents alphabetic random tokens from matching only because OCR letters resemble digits.
  - The accepted-sample regression for `box/top/aip`; without it, a stricter alias patch can silently break a previously accepted live solve.

## 2026-04-29 - ClaimCoin OCR latency guard and turbo-first fast profile

- Trigger evidence:
  - ClaimCoin run-loop produced live `accepted_success` samples but anti-bot OCR latency had outliers from roughly `76s` to `99s`.
  - Warmup stats showed normal solves around `6-7s`, but max cycle time reached `122.18s` and average solver time was pulled up by Tesseract spikes.
- Files touched:
  - `src/antibot_image_solver/ocr.py`
  - `src/antibot_image_solver/solver.py`
  - `tests/test_ocr_runtime.py`
  - `tests/test_solver_hybrid.py`
  - `tests/test_capture.py`
  - `README.md`
- What changed:
  - Added `ANTIBOT_OCR_TIMEOUT_SECONDS`, default `3.0`, and passed it to every Tesseract subprocess call.
  - Added `turbo` OCR profile with fewer preprocessing/PSM passes.
  - Made `fast` option-image solving try `turbo` first, but only accept a result when confidence is at least `0.56`; otherwise it falls back to the fuller `fast` OCR path.
- Why this exists:
  - The goal is to reduce easy-case solve time and cap worst-case OCR stalls without sacrificing accepted ClaimCoin samples.
  - Benchmark on the latest 30 live accepted ClaimCoin captures after the final correction pass: `30/30` replay matches, average `10.87s`, median `8.74s`, min `1.98s`, max `42.44s`, with `9` turbo accepts and `21` fallbacks.
  - Added ClaimCoin animal OCR corrections from live rejected/accepted samples, including panda/fox/deer and elephant/monkey confusions.
- Do not casually remove:
  - The confidence gate on turbo results. Lower thresholds around `0.55` replayed accepted captures incorrectly on two live samples.
  - The Tesseract timeout. It is the guard against long OCR spikes.

## 2026-04-29 - ddddocr offline benchmark lane

- Trigger evidence:
  - Boskuu asked whether replacing Tesseract with `ddddocr` could improve ClaimCoin AntiBot accuracy toward 98%++.
  - Live post-fallback rejects still showed OCR ambiguity and tie cases, especially id `527`.
- Files touched:
  - `tools/benchmark_ddddocr_claimcoin.py`
- What changed:
  - Added an offline benchmark script that runs `ddddocr` on stored ClaimCoin capture JSON, compares new ordered ids against accepted-sample ground truth, and writes JSONL output for review.
  - Installed `ddddocr` only in the project venv for testing. It is not promoted to a runtime dependency yet.
- Benchmark result:
  - `accepted_fail_ids` set: 19/19 errors, 0 accepted passes.
  - `rejects` set: 66/66 errors.
  - `latest_accepted` guard set: 80/80 errors, 0 accepted passes.
  - Root cause: direct `ddddocr` OCR outputs mostly concatenated/noisy strings without token separators, e.g. `zulzPzg`, `3av9c9`, `cuppugwjo`, so the current three-token matcher cannot extract ordered instruction tokens.
- Decision:
  - Do not replace Tesseract with raw `ddddocr`.
  - If revisited, use `ddddocr` only as a low-level character evidence source with a separate segmentation/sequence alignment layer, not as a drop-in OCR provider.
- Do not casually remove:
  - The negative benchmark note. It prevents re-trying raw ddddocr as a drop-in and wasting live accuracy.

## 2026-04-29 - ClaimCoin ambiguity tie-breaker pass

- Trigger evidence:
  - Live target was raised to 98%++ after post-patch rates fluctuated; newest rejects showed ambiguous/tie scoring rather than total OCR failure.
  - Example id `527`: `best_score == second_best_score`, so the matcher picked a tied order and submitted it.
- Files touched:
  - `src/antibot_image_solver/matcher.py`
  - `src/antibot_image_solver/normalize.py`
  - `tests/test_matcher.py`
- What changed:
  - Tightened numeric-alias matching so alphabetic instruction tokens no longer get boosted just because an option OCR candidate contains a digit. Numeric aliases now apply only when the instruction token itself is numeric or number-word-like.
  - Increased fuzzy text evidence weight from `25` to `100`, so close alphabetic OCR like `plg -> pig`, `cmt -> cat`, or `w3t -> wet` can beat weak digit-alias matches.
  - Added narrow live-derived OCR corrections for common accepted-regression families: pig/cat, run/rib, brown/yellow/blue, hotel/bag/flat, fox, and job-style confusions.
- Verification:
  - Full test suite: `31 passed`.
  - Stored-debug full-history replay: accepted regression improved to `472/477 = 98.95%` with only five accepted mismatches left (`145, 196, 276, 397, 458`).
  - Post-id-480 replay: accepted `56/56 = 100%`; post-id-517 replay: accepted `25/25 = 100%`.
  - Reject analysis changed `47/67` historical reject answers, including recent ids `506, 513, 514, 537, 541`; this is not proof of correctness by itself, but it confirms the resolver changes ambiguous outputs instead of leaving stale rejected answers untouched.
- Do not casually remove:
  - The narrower numeric-alias gate. Broad digit aliases were the root cause of many accepted-regression mismatches.
  - The narrow live OCR mappings. They are grounded in stored accepted captures and should remain regression-tested before edits.


## 2026-04-29 - ClaimCoin manual AntiBot labeling queue

- Trigger evidence:
  - Boskuu wants a proper manual-label workflow for AntiBot question/option images so future Tesseract and matcher tuning can use ground-truth labels, not guesses.
  - The target flow should prioritize rejected cases first, support 3 or 4 options automatically, ask whether solver reads are already correct using `Y/n/skip`, and keep skipped cases in queue.
- Files touched:
  - `tools/label_claimcoin_antibot.py`
- What changed:
  - Added an offline labeling helper with commands:
    - `export --priority rejected --limit N`
    - `label-next`
    - `stats`
  - Export decodes raw capture JSON base64 images into `state/antibot-labeling/images/<case_id>/` and writes queue JSON into `state/antibot-labeling/queue/`.
  - `label-next` shows question image path, solver OCR, each option image path, solver option OCR, and prompts only `Y/n/skip`. If `n`, the user enters the corrected text; if `skip`, the case remains in queue.
  - Correct order is auto-derived from labeled question tokens and option texts, then reviewed with `Y/n/skip`; manual order can be entered when needed.
  - Labeled cases move from `queue/` to `labeled/`; raw capture JSON is never deleted.
- Verification:
  - Script byte-compiled successfully.
  - Export smoke test created two rejected queue cases and decoded images: `claimcoin_000650` and `claimcoin_000541`.
  - `stats` reported queue=2, labeled=0, skipped=0.
- Do not casually remove:
  - The raw-capture preservation rule. Queue files can move, but source captures are evidence and must remain auditable.

## 2026-04-29 - ClaimCoin labeling visual preview

- Trigger evidence:
  - Boskuu asked for an easier labeling flow where images can be viewed while labeling, because plain SSH terminals do not display PNGs inline reliably.
- Files touched:
  - `tools/label_claimcoin_antibot.py`
- What changed:
  - Added `show-next` to generate a single contact sheet PNG for the next queue case under `state/antibot-labeling/preview/`.
  - Added `web-preview --limit N` to generate a read-only HTML gallery at `state/antibot-labeling/web/index.html`, using generated contact sheets for queued cases.
- Verification:
  - Script byte-compiled successfully.
  - `show-next` generated `state/antibot-labeling/preview/claimcoin_000541.png`.
  - `web-preview --limit 5` generated preview contact sheets and `state/antibot-labeling/web/index.html`.
- Do not casually remove:
  - The terminal labeling flow. Web preview is read-only by design for now; labels still move through `label-next` to avoid accidental browser-side writes.

## 2026-04-29 - ClaimCoin private web label studio

- Trigger evidence:
  - Boskuu wanted a proper interactive web labeling UI with stats, queue export, inline images, and labeling actions, preferably reachable through Cloudflared tunnel.
- Files touched:
  - `tools/label_claimcoin_web.py`
  - `pyproject.toml`
- What changed:
  - Added a FastAPI private label studio with token auth, queue stats, export form, case list, gallery, image serving, and case labeling form.
  - Label form shows question/option images inline, prefilled solver reads, checkboxes for solver-correct review, editable manual labels, and final order input.
  - Added `python-multipart` dependency for FastAPI form handling.
- Verification:
  - Local app started on `127.0.0.1:8765` in screen `claimlabel-web`.
  - Local health `GET /health` returned `{"ok": true}`.
  - Local HTML page rendered `ClaimCoin AntiBot Label Studio` with token auth.
  - Cloudflared quick tunnel was attempted in screen `claimlabel-tunnel`, but the generated trycloudflare URLs returned Cloudflare-side `404` and did not route to the local app, despite cloudflared reporting registered tunnel connections. Treat this as a tunnel routing blocker, not an app failure.
- Do not casually remove:
  - Token auth. Even quick tunnel URLs must not expose labeling writes without a secret token.
