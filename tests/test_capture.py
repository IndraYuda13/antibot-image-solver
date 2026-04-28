import json

import pytest

from antibot_image_solver.capture import CaptureRequest, CaptureValidationError, persist_capture
from antibot_image_solver.models import AntibotChallenge, SolveDebug, SolveResult
from antibot_image_solver.solver import solve_challenge


class DummyOutcome:
    ordered_ids = ["b", "a"]
    ordered_candidates = ["cat", "dog"]
    indexes_1based = [2, 1]
    confidence = 0.91
    tokens_detected = ["cat", "dog"]
    instruction_token_sets = [["cat", "dog"]]
    option_ocr = {}
    option_forms = {}
    best_score = 11
    second_best_score = 4


def test_persist_capture_writes_record_and_index(tmp_path):
    challenge = AntibotChallenge(
        instruction_image_base64="aW5zdHJ1Y3Rpb24=",
        candidates=["dog", "cat"],
        domain_hint="claimcoin",
        request_id="req-123",
    )
    result = SolveResult(
        success=True,
        status="solved",
        ordered_candidates=["cat", "dog"],
        indexes_1based=[2, 1],
        confidence=0.88,
        family="animals",
        tokens_detected=["cat", "dog"],
        debug=SolveDebug(instruction_ocr=["cat dog"]),
    )

    meta = persist_capture(
        challenge,
        result,
        CaptureRequest(output_dir=str(tmp_path), verdict="success", source="pytest", tags=["bench"]),
        include_debug=True,
    )

    record = json.loads((tmp_path / "req-123" / "record.json").read_text())
    index_line = json.loads((tmp_path / "index.jsonl").read_text().strip())

    assert meta["record_path"].endswith("req-123/record.json")
    assert record["verdict"] == "success"
    assert record["challenge"]["instruction_image_base64"] == "aW5zdHJ1Y3Rpb24="
    assert record["result"]["debug"]["instruction_ocr"] == ["cat dog"]
    assert index_line["challenge_id"] == "req-123"
    assert index_line["family"] == "animals"


def test_persist_capture_rejects_unknown_verdict(tmp_path):
    challenge = AntibotChallenge(instruction_image_base64="aGVsbG8=", candidates=["dog"])
    result = SolveResult(success=False, status="uncertain")

    with pytest.raises(CaptureValidationError):
        persist_capture(challenge, result, CaptureRequest(output_dir=str(tmp_path), verdict="bad-label"))


def test_solve_challenge_attaches_capture(monkeypatch, tmp_path):
    monkeypatch.setattr("antibot_image_solver.solver.ocr_candidates_from_base64", lambda _, **kwargs: ["cat dog"])
    monkeypatch.setattr("antibot_image_solver.solver.solve_from_text_candidates", lambda *_: DummyOutcome())

    result = solve_challenge(
        AntibotChallenge(instruction_image_base64="aGVsbG8=", candidates=["dog", "cat"], request_id="solve-1"),
        capture=CaptureRequest(output_dir=str(tmp_path), verdict="success", source="pytest"),
    )

    assert result.capture is not None
    assert result.capture["record_path"].endswith("solve-1/record.json")
    assert (tmp_path / "solve-1" / "record.json").exists()
