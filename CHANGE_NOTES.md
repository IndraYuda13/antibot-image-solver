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
