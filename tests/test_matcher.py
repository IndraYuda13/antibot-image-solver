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


def test_claimcoin_reject_confusions_pick_pin_org_bk_order():
    entries = [
        MatchEntry(id="6592", display="slot-pin", candidates=["pin", "pln", "—_"], forms=canonical_forms("pin") | canonical_forms("pln") | canonical_forms("—_")),
        MatchEntry(id="6756", display="slot-bk", candidates=["bk", "a", "_"], forms=canonical_forms("bk") | canonical_forms("a") | canonical_forms("_")),
        MatchEntry(id="8463", display="slot-org", candidates=["Org", "a"], forms=canonical_forms("Org") | canonical_forms("a")),
    ]
    result = solve_from_hypotheses(["pnk, org, blk.", "pak, org, ik"], entries)
    assert result.ordered_ids == ["6592", "8463", "6756"]


def test_claimcoin_reject_confusions_pick_ok_ww_yay_order():
    entries = [
        MatchEntry(id="3457", display="slot-yay", candidates=["yay", "Vely", "a"], forms=canonical_forms("yay") | canonical_forms("Vely") | canonical_forms("a")),
        MatchEntry(id="4758", display="slot-ww", candidates=["Ww", "_"], forms=canonical_forms("Ww") | canonical_forms("_")),
        MatchEntry(id="7800", display="slot-ok", candidates=["Ok", "—_"], forms=canonical_forms("Ok") | canonical_forms("—_")),
    ]
    result = solve_from_hypotheses(["OK, |UV, yay", "Ox, IUV, YAY"], entries)
    assert result.ordered_ids == ["7800", "4758", "3457"]


def test_claimcoin_accepted_confusions_keep_box_top_aip_order():
    entries = [
        MatchEntry(id="2541", display="slot-cvp", candidates=["Cvp", "cvp", "‘cyp", "a"], forms=canonical_forms("Cvp") | canonical_forms("cvp") | canonical_forms("‘cyp") | canonical_forms("a")),
        MatchEntry(id="3838", display="slot-boe", candidates=["b0", "Oe", "nf", "‘bOe", "—"], forms=canonical_forms("b0") | canonical_forms("Oe") | canonical_forms("nf") | canonical_forms("‘bOe") | canonical_forms("—")),
        MatchEntry(id="9651", display="slot-op", candidates=["ip", "op", "ty", "fp", "_"], forms=canonical_forms("ip") | canonical_forms("op") | canonical_forms("ty") | canonical_forms("fp") | canonical_forms("_")),
    ]
    result = solve_from_hypotheses(["box, top, aip", "box, top, aup"], entries)
    assert result.ordered_ids == ["3838", "9651", "2541"]


def test_claimcoin_tie_breaker_prefers_alpha_evidence_over_numeric_aliases():
    entries = [
        MatchEntry(id="9705", display="slot-off", candidates=["off", "O"], forms=canonical_forms("off") | canonical_forms("O")),
        MatchEntry(id="8519", display="slot-mo", candidates=["M0", "mo"], forms=canonical_forms("M0") | canonical_forms("mo")),
        MatchEntry(id="1526", display="slot-bad", candidates=["bad"], forms=canonical_forms("bad")),
    ]
    result = solve_from_hypotheses(["ort, M0, bad"], entries)
    assert result.ordered_ids == ["9705", "8519", "1526"]


def test_claimcoin_tie_breaker_repairs_common_live_words():
    entries = [
        MatchEntry(id="7392", display="slot-pig", candidates=["plg", "ply"], forms=canonical_forms("plg") | canonical_forms("ply")),
        MatchEntry(id="7773", display="slot-cat", candidates=["cmt"], forms=canonical_forms("cmt")),
        MatchEntry(id="4440", display="slot-bat", candidates=["‘bat"], forms=canonical_forms("‘bat")),
    ]
    result = solve_from_hypotheses(["pig, cat, bat"], entries)
    assert result.ordered_ids == ["7392", "7773", "4440"]


def test_claimcoin_tie_breaker_repairs_hotel_bag_flat_family():
    entries = [
        MatchEntry(id="7016", display="slot-hotel", candidates=["hot3l", "hOtsl"], forms=canonical_forms("hot3l") | canonical_forms("hOtsl")),
        MatchEntry(id="7648", display="slot-bag", candidates=["beg", "bes"], forms=canonical_forms("beg") | canonical_forms("bes")),
        MatchEntry(id="7963", display="slot-flat", candidates=["Filght", "fight"], forms=canonical_forms("Filght") | canonical_forms("fight")),
    ]
    result = solve_from_hypotheses(["notel, baa, flat"], entries)
    assert result.ordered_ids == ["7016", "7648", "7963"]
