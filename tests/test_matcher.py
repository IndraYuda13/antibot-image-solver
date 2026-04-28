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


def test_claimcoin_animal_ocr_confusions_pick_panda_fox_deer_order():
    entries = [
        MatchEntry(id="deer", display="slot-deer", candidates=["d33r", "ee"], forms=canonical_forms("d33r") | canonical_forms("ee")),
        MatchEntry(id="fox", display="slot-fox", candidates=["f0x", "fOx.", "fox."], forms=canonical_forms("f0x") | canonical_forms("fOx.") | canonical_forms("fox.")),
        MatchEntry(id="panda", display="slot-panda", candidates=["pende", "pGnde", "pend?"], forms=canonical_forms("pende") | canonical_forms("pGnde") | canonical_forms("pend?")),
    ]
    result = solve_from_hypotheses(["panda, 10X, aver", "para, TOX, Geir"], entries)
    assert result.ordered_ids == ["panda", "fox", "deer"]


def test_claimcoin_elephant_ocr_confusions_pick_tiger_elephant_monkey_order():
    entries = [
        MatchEntry(id="tiger", display="slot-tiger", candidates=["Tig3r", "esr"], forms=canonical_forms("Tig3r") | canonical_forms("esr")),
        MatchEntry(id="elephant", display="slot-elephant", candidates=["sreph@nt", "sephe nt", "meaphimt"], forms=canonical_forms("sreph@nt") | canonical_forms("sephe nt") | canonical_forms("meaphimt")),
        MatchEntry(id="monkey", display="slot-monkey", candidates=["MmOnk3y", "mOnk3y"], forms=canonical_forms("MmOnk3y") | canonical_forms("mOnk3y")),
    ]
    result = solve_from_hypotheses(["Tiger, eepnany, MONKEY"], entries)
    assert result.ordered_ids == ["tiger", "elephant", "monkey"]


def test_confidence_is_positive_on_clear_match():
    result = solve_from_text_candidates(["one two three"], ["three", "one", "two"])
    assert result.confidence > 0
