# ClaimCoin Low-Confidence Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise ClaimCoin AntiBot live accuracy toward 98%++ by adding a guarded fallback only when the fast solver is low-confidence.

**Architecture:** Keep the existing fast path unchanged for confident cases. When `ANTIBOT_OCR_PROFILE=fast` and an option-image solve returns confidence below a configurable threshold, run one slower `full` OCR pass and choose it only if it materially improves confidence. Record the fallback decision in `SolveResult.meta` so live captures can be audited.

**Tech Stack:** Python 3.12, existing `antibot_image_solver` package, pytest, systemd service `claimcoin-antibot.service`.

---

### Task 1: Add fallback configuration helpers

**Files:**
- Modify: `src/antibot_image_solver/solver.py`
- Test: `tests/test_solver_hybrid.py`

- [ ] Add `get_low_confidence_threshold()` reading `ANTIBOT_LOW_CONFIDENCE_THRESHOLD`, default `0.50`, clamped to `0.0..0.99`.
- [ ] Add `get_full_fallback_min_gain()` reading `ANTIBOT_FULL_FALLBACK_MIN_GAIN`, default `0.08`, clamped to `0.0..0.50`.
- [ ] Add focused tests for invalid env fallback to defaults.

### Task 2: Add full OCR fallback after low-confidence fast solve

**Files:**
- Modify: `src/antibot_image_solver/solver.py`
- Test: `tests/test_solver_hybrid.py`

- [ ] In `solve_challenge()`, after turbo->fast result, if success and confidence is below threshold, run `_solve_challenge_once(..., ocr_profile="full")`.
- [ ] Accept full result only if it succeeds and improves confidence by at least min gain.
- [ ] If accepted, add meta fields: `fallback_profile="full"`, `fallback_reason="low_confidence"`, `fallback_from_profile="fast"`, `fallback_from_confidence=<old>`.
- [ ] If rejected, keep fast result but add meta fields: `fallback_profile="full"`, `fallback_reason="low_confidence_not_improved"`, `fallback_candidate_confidence=<full confidence>`.
- [ ] Add tests covering accepted full fallback and rejected full fallback.

### Task 3: Verify against history and live service

**Files:**
- Existing evaluator: `tools/evaluate_claimcoin_history.py`
- Existing notes: `CHANGE_NOTES.md`

- [ ] Run `python -m pytest -q` and expect all tests pass.
- [ ] Run stored-debug evaluator or focused regression where useful.
- [ ] Restart `claimcoin-antibot.service` and confirm `/health` OK.
- [ ] Update `CHANGE_NOTES.md` with trigger evidence, touched files, verification, and do-not-remove notes.
- [ ] Commit and push.
