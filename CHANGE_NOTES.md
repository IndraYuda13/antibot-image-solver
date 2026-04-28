# Change Notes

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
