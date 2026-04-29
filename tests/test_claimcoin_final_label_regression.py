from __future__ import annotations

from antibot_image_solver.matcher import MatchEntry, solve_from_hypotheses
from antibot_image_solver.normalize import canonical_forms


def _entry(option_id: str, candidates: list[str]) -> MatchEntry:
    forms = set()
    for candidate in candidates:
        forms |= canonical_forms(candidate)
    return MatchEntry(id=option_id, display=candidates[0], candidates=candidates, forms=forms)


def _solve(question_ocr: list[str], options: dict[str, list[str]]) -> list[str]:
    return solve_from_hypotheses(question_ocr, [_entry(k, v) for k, v in options.items()]).ordered_ids


def test_claimcoin_000145_stored_debug_matches_manual_label():
    assert _solve(
        ["TOY, Mar, cay"],
        {"4162": ["ep"], "4373": ["myejt"], "6195": ["wy"]},
    ) == ["6195", "4373", "4162"]


def test_claimcoin_000276_stored_debug_matches_manual_label():
    assert _solve(
        ["Jol, Ill, soo."],
        {"1231": ["101"], "2104": ["Ih"], "6818": ["500"]},
    ) == ["1231", "2104", "6818"]


def test_claimcoin_000397_stored_debug_matches_manual_label():
    assert _solve(
        ["crab, kelly, star Sse,"],
        {"6649": ["Aerio"], "7272": ["ae"], "9763": ["ily"]},
    ) == ["7272", "9763", "6649"]


def test_claimcoin_000702_stored_debug_matches_manual_label_with_noisy_lower_candidate():
    assert _solve(
        ["arc, or, row"],
        {"3665": ["mc", "or", "a"], "3834": ["row", "Ow", "a"], "6916": ["cir", "dr", "_"]},
    ) == ["3665", "6916", "3834"]


def test_claimcoin_000723_stored_debug_matches_accepted_success_order():
    assert _solve(
        ["eCream, Warer, Ke"],
        {"3489": ["1c3cr34m"], "4188": ["3"], "9337": ["wr"]},
    ) == ["3489", "9337", "4188"]
