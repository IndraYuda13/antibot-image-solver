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


def test_claimcoin_post_tuning_reject_labels_match_manual_ground_truth():
    assert _solve(
        ["sad, sky, say"],
        {"3950": ["Dky"], "5417": ["say"], "8140": ["5@q"]},
    ) == ["8140", "3950", "5417"]
    assert _solve(
        ["yum, you, yew"],
        {"2064": ["yvM"], "4689": ["pw"], "5721": ["yOv"]},
    ) == ["2064", "5721", "4689"]
    assert _solve(
        ["air, hot, fog"],
        {"1922": ["ew"], "2363": ["hot"], "3541": ["£04"]},
    ) == ["1922", "2363", "3541"]
    assert _solve(
        ["od, rot, wad"],
        {"4943": ["nid"], "5775": ["ned"], "6156": ["pot"]},
    ) == ["4943", "6156", "5775"]


def test_claimcoin_already_labeled_regressions_do_not_need_requeue():
    assert _solve(
        ["aT, &VE, 299", "Lat, eve, 299", "OT, ONG, 24g"],
        {"1826": ["3e@t", "3@t", "set"], "3617": ["3u3", "ua", "dud"], "9347": ["39g", "399", "499", "gg"]},
    ) == ["1826", "3617", "9347"]
    assert _solve(
        ["wir, 124, ice"],
        {"1969": ["wir"], "4015": ["\\c3"], "9275": ["te"]},
    ) == ["1969", "9275", "4015"]


def test_claimcoin_000489_accepted_raw_sky_ice_air_regression():
    assert _solve(
        ["SKY, IC, alr"],
        {"7130": ["oky"], "4316": ["\\c3"], "6305": ["ew"]},
    ) == ["7130", "4316", "6305"]


def test_claimcoin_bulk_manual_labels_from_relabeling_pass():
    cases = [
        (["TOX, MONKEY, ani"], {"1916": ["mOnk3y"], "2187": ["i"], "4432": ["Gn"]}, ["2187", "1916", "4432"]),
        (["ely, try, sit"], {"2604": ["Bit"], "6728": ["+r"], "8205": ["ay"]}, ["8205", "6728", "2604"]),
        (["aw, stier, faiher"], {"1578": ["girf"], "2482": ["f@th3r"], "5232": ["alalar"]}, ["1578", "5232", "2482"]),
        (["0,2,3", "0,2,35", "0, 2,3 °"], {"1490": ["0", "wd", "tw"], "3328": ["z3r0", "2Br0", "73r0"], "9131": ["thr33", "thr33,"]}, ["3328", "1490", "9131"]),
        (["ner, ram, rom"], {"2233": ["rm"], "5527": ["<"], "5606": ["mn"]}, ["5527", "2233", "5606"]),
        (["4°13", "413°", "4, |, 9", "41,9)"], {"6392": ["s3v3n", "s3v3n_"], "8586": ["thr33", "thr33-", "33"], "9749": ["{Our", "{oor", "four"]}, ["9749", "6392", "8586"]),
        (["ort, Nor, DA"], {"1927": ["not"], "2444": ["bl"], "7020": ["Off"]}, ["7020", "1927", "2444"]),
        (["air, ice, dew"], {"1304": ["ral"], "2067": ["Ley"], "2943": ["@r"]}, ["2943", "2067", "1304"]),
        (["dad, mom, man"], {"1108": ["mar\""], "1899": ["d@a"], "8364": ["wer"]}, ["1899", "1108", "8364"]),
        (["starrisn, crap, 19"], {"1487": ["o@b"], "2019": ["fish"], "4802": ["st@rkish"]}, ["4802", "1487", "2019"]),
        (["424, try, te"], {"3558": ["t03"], "9226": ["teg"], "9488": ["at"]}, ["9226", "9488", "3558"]),
        (["win, get, set"], {"5946": ["opt"], "9253": ["win"], "9483": ["3"]}, ["9253", "5946", "9483"]),
        (["Seven, TVG, SIX"], {"1686": ["4"], "4017": ["6"], "4022": ["5"]}, ["1686", "4022", "4017"]),
        (["pad, pan, pen"], {"1137": ["pen"], "2882": ["p3n"], "2936": ["p@a"]}, ["2936", "1137", "2882"]),
    ]
    for question, options, expected in cases:
        assert _solve(question, options) == expected


def test_claimcoin_latest_live_reject_labels_from_772_window():
    assert _solve(
        ["class, desh, bag"],
        {"5482": ["085"], "6852": ["dé@ss"], "7756": ["b@g"]},
    ) == ["6852", "5482", "7756"]
    assert _solve(
        ["net, 9pu, api"],
        {"1560": ["gpu"], "8170": ["@y\\"], "9809": ["nat"]},
    ) == ["9809", "1560", "8170"]
    assert _solve(
        ["uti, urn, Ulu"],
        {"1706": ["vn"], "2188": ["vt"], "3378": ["viv"]},
    ) == ["2188", "1706", "3378"]


def test_claimcoin_post_813_live_reject_labels():
    assert _solve(
        ["toy, lid, key"],
        {"3219": ["iy", "fy", "{Oy", "hy"], "3595": ["hay", "hay,", "Rdy"], "5361": ["Md", "i1d", "itd"]},
    ) == ["3219", "5361", "3595"]
    assert _solve(
        ["two, One, seven", "two, one, seven"],
        {"3777": ["Ly", "v", "l", "1", "7"], "3857": ["7", "Tt"], "8937": ["2"]},
    ) == ["8937", "3777", "3857"]
    assert _solve(
        ["jin, jot, joy", "jin, jot. joy"],
        {"4378": ["jOy", "joy"], "6673": ["int", "jt"], "7144": ["ln", "jn"]},
    ) == ["7144", "6673", "4378"]
    assert _solve(
        ["hit. hen, hot", "hit. hen. hot"],
        {"1565": [")", "vr", "Vit", "Wr"], "2299": ["ht", "At", "vir"], "7497": ["h8n", "AB", "|", "‘ABn,"]},
    ) == ["2299", "7497", "1565"]
