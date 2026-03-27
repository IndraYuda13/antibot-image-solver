from antibot_image_solver.matcher import MatchEntry, solve_from_hypotheses, solve_from_text_candidates
from antibot_image_solver.normalize import canonical_forms


def test_solve_from_text_candidates_animals():
    result = solve_from_text_candidates(
        ["dog, cat, mouse", "DOG CAT MOUSE"],
        ["mouse", "dog", "cat"],
    )
    assert result.ordered_candidates == ["dog", "cat", "mouse"]
    assert result.indexes_1based == [2, 3, 1]


def test_solve_from_hypotheses_arithmetic_family():
    entries = [
        MatchEntry(id="a", display="slot-a", candidates=["2*4", "24"], forms=canonical_forms("2*4") | canonical_forms("24")),
        MatchEntry(id="b", display="slot-b", candidates=["3+3", "33"], forms=canonical_forms("3+3") | canonical_forms("33")),
        MatchEntry(id="c", display="slot-c", candidates=["9-4", "94"], forms=canonical_forms("9-4") | canonical_forms("94")),
    ]
    result = solve_from_hypotheses(["8, 6, 5", "8 6 5"], entries)
    assert result.ordered_ids == ["a", "b", "c"]


def test_confidence_is_positive_on_clear_match():
    result = solve_from_text_candidates(["one two three"], ["three", "one", "two"])
    assert result.confidence > 0
