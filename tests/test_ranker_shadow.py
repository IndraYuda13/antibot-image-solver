from __future__ import annotations

import json

from antibot_image_solver.models import SolveResult
from antibot_image_solver.ranker_shadow import build_shadow_decision, append_shadow_decision


def test_build_shadow_decision_preserves_production_order():
    result = SolveResult(success=True, status="solved", ordered_ids=["a", "b", "c"], confidence=0.88)

    payload = build_shadow_decision(result, request_id="case-1")

    assert payload["schema_version"] == "antibot-image-solver.ranker-shadow.v1"
    assert payload["mode"] == "shadow_no_submit"
    assert payload["no_submit"] is True
    assert payload["production_order"] == ["a", "b", "c"]
    assert payload["shadow_order"] == ["a", "b", "c"]
    assert payload["would_override"] is False


def test_append_shadow_decision_writes_jsonl_without_mutating_result(tmp_path):
    result = SolveResult(success=True, status="solved", ordered_ids=["x", "y"], confidence=0.5)
    path = tmp_path / "shadow.jsonl"

    append_shadow_decision(path, result, request_id="case-2")

    assert result.ordered_ids == ["x", "y"]
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["request_id"] == "case-2"
    assert rows[0]["no_submit"] is True
