from __future__ import annotations

import json
import sys

from antibot_image_solver.models import SolveDebug, SolveResult
from antibot_image_solver.ranker_shadow import build_shadow_decision


def test_build_shadow_decision_uses_external_provider_without_mutating_production(tmp_path):
    provider = tmp_path / "provider.py"
    provider.write_text(
        "import json, sys\n"
        "payload=json.load(sys.stdin)\n"
        "assert payload['production_order'] == ['a', 'b', 'c']\n"
        "print(json.dumps({'shadow_order':['c','b','a'],'would_override': True,'override_probability':0.91,'ai_confidence':0.77}))\n"
    )
    result = SolveResult(
        success=True,
        status="solved",
        ordered_ids=["a", "b", "c"],
        confidence=0.88,
        debug=SolveDebug(instruction_ocr=["ice, pan, tea"], option_ocr={"a": ["ice"], "b": ["pan"], "c": ["tea"]}),
    )

    payload = build_shadow_decision(result, request_id="case-1", provider_command=f"{sys.executable} {provider}")

    assert result.ordered_ids == ["a", "b", "c"]
    assert payload["production_order"] == ["a", "b", "c"]
    assert payload["shadow_order"] == ["c", "b", "a"]
    assert payload["would_override"] is True
    assert payload["no_submit"] is True
    assert payload["status"] == "provider_decision_logged"


def test_build_shadow_decision_falls_back_when_provider_fails():
    result = SolveResult(success=True, status="solved", ordered_ids=["a"], confidence=0.5)

    payload = build_shadow_decision(result, request_id="case-2", provider_command="/no/such/provider")

    assert payload["production_order"] == ["a"]
    assert payload["shadow_order"] == ["a"]
    assert payload["would_override"] is False
    assert payload["status"] == "provider_error_fallback"
    assert payload["no_submit"] is True
