from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import permutations
from typing import Iterable, Optional

from antibot_image_solver.normalize import NUMBER_WORDS, WORD_NUMBERS, canonical_forms, normalize_letters


class MatchError(RuntimeError):
    pass


@dataclass
class MatchEntry:
    id: str
    display: str
    candidates: list[str]
    forms: set[str]


@dataclass
class MatchOutcome:
    ordered_ids: list[str]
    ordered_candidates: list[str]
    indexes_1based: list[int]
    tokens_detected: list[str]
    best_score: int
    second_best_score: int
    confidence: float
    instruction_token_sets: list[list[str]]
    option_ocr: dict[str, list[str]]
    option_forms: dict[str, list[str]]


def extract_instruction_token_sets(candidates: list[str], option_count: int) -> list[list[str]]:
    token_sets: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        cleaned = candidate.replace("\n", " ").strip()
        for splitter in (",", None):
            if splitter == ",":
                parts = [part.strip() for part in cleaned.split(",") if part.strip()]
            else:
                parts = [part.strip() for part in cleaned.split() if part.strip()]
            if len(parts) == option_count:
                key = tuple(parts)
                if key not in seen:
                    seen.add(key)
                    token_sets.append(parts)
    return token_sets


def fuzzy_text_score(token: str, candidates: Iterable[str]) -> float:
    best = 0.0
    want = token.lower().strip()
    for candidate in candidates:
        got = candidate.lower().strip()
        if not want or not got:
            continue
        best = max(best, SequenceMatcher(None, want, got).ratio())
    return best


def _is_numeric_alias(form: str) -> bool:
    return form.isdigit() or form in NUMBER_WORDS.values()


def _allow_numeric_alias_match(token: str, option_candidates: Iterable[str]) -> bool:
    token_alpha = normalize_letters(token).strip(", ")
    if any(ch.isdigit() for ch in token):
        return True
    return token_alpha in WORD_NUMBERS or token_alpha in NUMBER_WORDS.values()


def token_option_score(token: str, want_forms: set[str], option_candidates: list[str], option_forms: set[str]) -> int:
    overlap = want_forms & option_forms
    if not _allow_numeric_alias_match(token, option_candidates):
        overlap = {form for form in overlap if not _is_numeric_alias(form)}
    score = len(overlap) * 100
    score += int(fuzzy_text_score(token, option_candidates) * 100)
    return score


def _build_entries_from_text_candidates(candidates: list[str]) -> list[MatchEntry]:
    entries: list[MatchEntry] = []
    for index, candidate in enumerate(candidates, 1):
        entries.append(
            MatchEntry(
                id=str(index),
                display=candidate,
                candidates=[candidate],
                forms=canonical_forms(candidate),
            )
        )
    return entries


def _calc_confidence(best_score: int, second_best_score: int, option_count: int) -> float:
    if best_score <= 0 or option_count <= 0:
        return 0.0
    ratio = min(1.0, best_score / max(1, option_count * 125))
    gap = max(0.0, (best_score - second_best_score) / max(1, best_score))
    return round(min(0.99, 0.55 * ratio + 0.45 * gap), 4)


def solve_from_hypotheses(
    instruction_candidates: list[str],
    entries: list[MatchEntry],
) -> MatchOutcome:
    if not instruction_candidates:
        raise MatchError("instruction OCR candidates are empty")
    if not entries:
        raise MatchError("no option entries provided")

    token_sets = extract_instruction_token_sets(instruction_candidates, len(entries))
    if not token_sets:
        raise MatchError(f"failed to extract instruction token set from OCR candidates: {instruction_candidates}")

    best: Optional[tuple[list[str], tuple[int, ...]]] = None
    best_score = -1
    second_best_score = -1

    for requested_tokens in token_sets:
        want_forms_list = [canonical_forms(token) for token in requested_tokens]
        for permutation in permutations(range(len(entries)), len(requested_tokens)):
            score = 0
            for token_index, option_index in enumerate(permutation):
                entry = entries[option_index]
                score += token_option_score(
                    requested_tokens[token_index],
                    want_forms_list[token_index],
                    entry.candidates,
                    entry.forms,
                )
            if score > best_score:
                second_best_score = best_score
                best_score = score
                best = (requested_tokens, permutation)
            elif score > second_best_score:
                second_best_score = score

    if best is None or best_score <= 0:
        debug = {entry.id: sorted(entry.forms)[:12] for entry in entries}
        raise MatchError(
            f"failed to match global anti-bot order; instruction={instruction_candidates} entries={debug}"
        )

    requested_tokens, best_perm = best
    ordered_ids = [entries[index].id for index in best_perm]
    ordered_candidates = [entries[index].display for index in best_perm]
    indexes_1based = [index + 1 for index in best_perm]
    confidence = _calc_confidence(best_score, second_best_score, len(entries))

    return MatchOutcome(
        ordered_ids=ordered_ids,
        ordered_candidates=ordered_candidates,
        indexes_1based=indexes_1based,
        tokens_detected=requested_tokens,
        best_score=best_score,
        second_best_score=max(0, second_best_score),
        confidence=confidence,
        instruction_token_sets=token_sets,
        option_ocr={entry.id: entry.candidates for entry in entries},
        option_forms={entry.id: sorted(entry.forms) for entry in entries},
    )


def solve_from_text_candidates(instruction_candidates: list[str], candidates: list[str]) -> MatchOutcome:
    return solve_from_hypotheses(instruction_candidates, _build_entries_from_text_candidates(candidates))
