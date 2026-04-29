from __future__ import annotations

from antibot_image_solver.matcher import MatchEntry, solve_from_hypotheses
from antibot_image_solver.normalize import canonical_forms


def _entry(option_id: str, text: str) -> MatchEntry:
    return MatchEntry(id=option_id, display=text, candidates=[text], forms=canonical_forms(text))


def _solve(question: str, options: dict[str, str]) -> list[str]:
    return solve_from_hypotheses([question], [_entry(k, v) for k, v in options.items()]).ordered_ids


def test_claimcoin_manual_label_color_family_regressions():
    assert _solve("bk, brn, wht", {"2398": "Wal", "3776": "brn", "7899": "bik"}) == ["7899", "3776", "2398"]


def test_claimcoin_manual_label_shape_family_regressions():
    assert _solve("arc, or, row", {"3665": "mc", "3834": "row", "6916": "cir"}) == ["3665", "6916", "3834"]


def test_claimcoin_manual_label_zoo_zip_zig_regressions():
    assert _solve("Zen, 2, Zr", {"1515": "z3n", "4619": "20r", "9761": "200"}) == ["1515", "9761", "4619"]
    assert _solve("Zul, zip, zig", {"1164": "ug", "1581": "zi", "4991": "2p"}) == ["1581", "4991", "1164"]


def test_claimcoin_manual_label_text_family_regressions():
    assert _solve("use, mix, add", {"3190": "m1x", "4983": "“3", "8177": "@da"}) == ["4983", "3190", "8177"]
    assert _solve("football, cricket, qole", {"2774": "f00tbell", "7003": "opt", "8981": "nick"}) == ["2774", "8981", "7003"]
    assert _solve("Pan, pai, ple", {"2608": "pen", "3697": "pis", "7112": "pey"}) == ["2608", "7112", "3697"]
