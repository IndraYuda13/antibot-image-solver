from __future__ import annotations

import json
import sys

from antibot_image_solver.models import SolveResult
from antibot_image_solver.solver import _maybe_append_ranker_shadow


def test_solver_shadow_hook_uses_provider_env_without_changing_order(monkeypatch, tmp_path):
    log_path = tmp_path / "shadow.jsonl"
    provider = tmp_path / "provider.py"
    provider.write_text(
        "import json, sys\n"
        "json.load(sys.stdin)\n"
        "print(json.dumps({'shadow_order':['z'],'would_override': True,'override_probability':0.8,'ai_confidence':0.7}))\n"
    )
    monkeypatch.setenv("ANTIBOT_RANKER_SHADOW_LOG", str(log_path))
    monkeypatch.setenv("ANTIBOT_RANKER_SHADOW_PROVIDER", f"{sys.executable} {provider}")
    result = SolveResult(success=True, status="solved", ordered_ids=["a"], confidence=0.6)

    _maybe_append_ranker_shadow(result, request_id="req-3")

    assert result.ordered_ids == ["a"]
    assert result.meta["ranker_shadow"]["shadow_order"] == ["z"]
    rows = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert rows[0]["would_override"] is True
    assert rows[0]["no_submit"] is True
