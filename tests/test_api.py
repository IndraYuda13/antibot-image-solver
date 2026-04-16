from fastapi.testclient import TestClient

from antibot_image_solver.api.app import app
from antibot_image_solver.models import SolveDebug, SolveResult


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "antibot-image-solver"


def test_solve_endpoint_returns_capture(monkeypatch, tmp_path):
    def fake_solve(challenge, *, debug=False, capture=None):
        assert challenge.request_id == "api-1"
        assert capture is not None
        return SolveResult(
            success=True,
            status="solved",
            ordered_candidates=["dog", "cat"],
            indexes_1based=[1, 2],
            confidence=0.93,
            family="animals",
            tokens_detected=["dog", "cat"],
            debug=SolveDebug(instruction_ocr=["dog cat"]),
            capture={
                "challenge_id": "api-1",
                "record_path": str(tmp_path / "api-1" / "record.json"),
                "index_path": str(tmp_path / "index.jsonl"),
            },
        )

    monkeypatch.setattr("antibot_image_solver.api.app.solve_challenge", fake_solve)

    response = client.post(
        "/solve/antibot-image",
        json={
            "instruction_image_base64": "aGVsbG8=",
            "candidates": ["dog", "cat"],
            "request_id": "api-1",
            "capture": {"output_dir": str(tmp_path), "verdict": "success", "tags": ["claimcoin"]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["capture"]["challenge_id"] == "api-1"
    assert body["solution"]["ordered_candidates"] == ["dog", "cat"]
