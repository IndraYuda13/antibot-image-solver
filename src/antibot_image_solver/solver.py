from __future__ import annotations

import os

from antibot_image_solver.capture import CaptureRequest, persist_capture
from antibot_image_solver.matcher import MatchEntry, MatchError, solve_from_hypotheses, solve_from_text_candidates
from antibot_image_solver.models import AntibotChallenge, SolveDebug, SolveResult
from antibot_image_solver.normalize import canonical_forms, guess_family
from antibot_image_solver.ocr import OcrRuntimeError, get_ocr_profile, ocr_candidates_from_base64


class SolverError(RuntimeError):
    pass


class SolverInputError(SolverError):
    pass


class SolverLowConfidenceError(SolverError):
    pass


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def get_low_confidence_threshold() -> float:
    return _env_float("ANTIBOT_LOW_CONFIDENCE_THRESHOLD", 0.50, minimum=0.0, maximum=0.99)


def get_full_fallback_min_gain() -> float:
    return _env_float("ANTIBOT_FULL_FALLBACK_MIN_GAIN", 0.08, minimum=0.0, maximum=0.50)


def _attach_capture(
    challenge: AntibotChallenge,
    result: SolveResult,
    capture: CaptureRequest | None,
    *,
    include_debug: bool,
) -> SolveResult:
    if capture is None:
        return result
    result.capture = persist_capture(challenge, result, capture, include_debug=include_debug)
    return result


def analyze_instruction_image(instruction_image_base64: str) -> dict:
    instruction_ocr = ocr_candidates_from_base64(instruction_image_base64)
    family = guess_family(instruction_ocr)
    tokens = []
    if instruction_ocr:
        from antibot_image_solver.matcher import extract_instruction_token_sets

        token_sets = extract_instruction_token_sets(instruction_ocr, 3)
        if token_sets:
            tokens = token_sets[0]
    return {
        "ocr": {
            "raw_variants": instruction_ocr,
            "best_text": instruction_ocr[0] if instruction_ocr else None,
        },
        "tokens": tokens,
        "family_guess": family,
    }


def _challenge_to_entries(challenge: AntibotChallenge, *, ocr_profile: str | None = None) -> list[MatchEntry]:
    entries: list[MatchEntry] = []
    for option in challenge.options:
        candidates = list(option.text_candidates)
        if not candidates:
            candidates = ocr_candidates_from_base64(option.image_base64, profile=ocr_profile)
        forms = set(option.canonical_forms)
        if not forms:
            for candidate in candidates:
                forms |= canonical_forms(candidate)
        display = option.id
        if candidates:
            display = candidates[0]
        entries.append(
            MatchEntry(
                id=option.id,
                display=display,
                candidates=candidates,
                forms=forms,
            )
        )
    return entries


def _solve_challenge_once(challenge: AntibotChallenge, *, debug: bool = False, ocr_profile: str | None = None) -> SolveResult:
    try:
        instruction_ocr = ocr_candidates_from_base64(challenge.instruction_image_base64, profile=ocr_profile)
    except OcrRuntimeError as exc:
        raise SolverError(str(exc)) from exc

    if not instruction_ocr:
        return SolveResult(
            success=False,
            status="uncertain",
            confidence=0.0,
            error_code="OCR_EMPTY",
            error_message="instruction OCR returned no candidates",
        )

    try:
        if challenge.options:
            entries = _challenge_to_entries(challenge, ocr_profile=ocr_profile)
            outcome = solve_from_hypotheses(instruction_ocr, entries)
        else:
            outcome = solve_from_text_candidates(instruction_ocr, challenge.candidates)
    except (MatchError, OcrRuntimeError) as exc:
        return SolveResult(
            success=False,
            status="uncertain",
            confidence=0.0,
            family=guess_family(instruction_ocr),
            tokens_detected=[],
            error_code="LOW_CONFIDENCE",
            error_message=str(exc),
            debug=SolveDebug(instruction_ocr=instruction_ocr),
        )

    debug_payload = None
    if debug:
        debug_payload = SolveDebug(
            instruction_ocr=instruction_ocr,
            instruction_token_sets=outcome.instruction_token_sets,
            option_ocr=outcome.option_ocr,
            option_forms=outcome.option_forms,
            best_score=outcome.best_score,
            second_best_score=outcome.second_best_score,
        )

    return SolveResult(
        success=True,
        status="solved",
        ordered_ids=outcome.ordered_ids,
        ordered_candidates=outcome.ordered_candidates,
        indexes_1based=outcome.indexes_1based,
        confidence=outcome.confidence,
        family=guess_family(outcome.tokens_detected),
        tokens_detected=outcome.tokens_detected,
        debug=debug_payload,
        meta={
            "domain_hint": challenge.domain_hint,
            "mode": "option_images" if challenge.options else "text_candidates",
            "ocr_profile": ocr_profile or get_ocr_profile(),
        },
    )


def _accept_turbo_result(result: SolveResult) -> bool:
    return result.success and result.confidence >= 0.56


def _maybe_full_fallback(challenge: AntibotChallenge, result: SolveResult, *, debug: bool) -> SolveResult:
    threshold = get_low_confidence_threshold()
    if not result.success or result.confidence >= threshold:
        return result

    fallback = _solve_challenge_once(challenge, debug=debug, ocr_profile="full")
    min_gain = get_full_fallback_min_gain()
    if fallback.success and fallback.confidence >= result.confidence + min_gain:
        fallback.meta.update(
            {
                "fallback_profile": "full",
                "fallback_reason": "low_confidence",
                "fallback_from_profile": result.meta.get("ocr_profile"),
                "fallback_from_confidence": result.confidence,
                "fallback_threshold": threshold,
                "fallback_min_gain": min_gain,
            }
        )
        return fallback

    result.meta.update(
        {
            "fallback_profile": "full",
            "fallback_reason": "low_confidence_not_improved",
            "fallback_candidate_confidence": fallback.confidence,
            "fallback_candidate_success": fallback.success,
            "fallback_threshold": threshold,
            "fallback_min_gain": min_gain,
        }
    )
    if fallback.error_code:
        result.meta["fallback_candidate_error_code"] = fallback.error_code
    return result


def solve_challenge(challenge: AntibotChallenge, *, debug: bool = False, capture: CaptureRequest | None = None) -> SolveResult:
    if not challenge.instruction_image_base64:
        raise SolverInputError("instruction_image_base64 is required")
    if not challenge.options and not challenge.candidates:
        raise SolverInputError("either options or candidates must be provided")

    profile = get_ocr_profile()
    if profile == "fast" and challenge.options:
        result = _solve_challenge_once(challenge, debug=debug, ocr_profile="turbo")
        if not _accept_turbo_result(result):
            result = _solve_challenge_once(challenge, debug=debug, ocr_profile="fast")
            result = _maybe_full_fallback(challenge, result, debug=debug)
    else:
        result = _solve_challenge_once(challenge, debug=debug, ocr_profile=profile)
    return _attach_capture(challenge, result, capture, include_debug=debug or capture is not None)
