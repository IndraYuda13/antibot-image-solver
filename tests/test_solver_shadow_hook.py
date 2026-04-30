from __future__ import annotations

import json

from antibot_image_solver.models import SolveResult
from antibot_image_solver.solver import _maybe_append_ranker_shadow


def test_maybe_append_ranker_shadow_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTIBOT_RANKER_SHADOW_LOG", raising=False)
    result = SolveResult(success=True, status="solved", ordered_ids=["a"])

    _maybe_append_ranker_shadow(result, request_id="req-1")

    assert "ranker_shadow" not in result.meta


def test_maybe_append_ranker_shadow_logs_when_enabled(monkeypatch, tmp_path):
    path = tmp_path / "shadow.jsonl"
    monkeypatch.setenv("ANTIBOT_RANKER_SHADOW_LOG", str(path))
    result = SolveResult(success=True, status="solved", ordered_ids=["a"])

    _maybe_append_ranker_shadow(result, request_id="req-2")

    assert result.ordered_ids == ["a"]
    assert result.meta["ranker_shadow"]["no_submit"] is True
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["request_id"] == "req-2"
