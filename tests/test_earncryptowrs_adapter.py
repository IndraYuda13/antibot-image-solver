from pathlib import Path

from antibot_image_solver.adapters.earncryptowrs import build_challenge_from_faucet_html, parse_faucet_form


FIXTURE = Path(__file__).parent / "fixtures" / "earncryptowrs_form.html"


def test_parse_faucet_form_extracts_instruction_and_options():
    html = FIXTURE.read_text(encoding="utf-8")
    form = parse_faucet_form(html)
    assert form.action.endswith("/faucet/verify/demo/ltc")
    assert form.csrf_token == "csrf-demo"
    assert form.server_token == "token-demo"
    assert form.wallet == "demo@example.com"
    assert len(form.challenge.options) == 3
    assert form.challenge.options[0].id == "1111"


def test_build_challenge_from_html_returns_domain_hint():
    html = FIXTURE.read_text(encoding="utf-8")
    challenge = build_challenge_from_faucet_html(html)
    assert challenge.domain_hint == "earncryptowrs"
    assert challenge.instruction_image_base64
