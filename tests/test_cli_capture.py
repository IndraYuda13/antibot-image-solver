import json

from antibot_image_solver.cli import main
from antibot_image_solver.models import SolveResult


def test_cli_solve_image_forwards_capture(monkeypatch, tmp_path, capsys):
    image_path = tmp_path / "instruction.png"
    image_path.write_bytes(b"img")

    def fake_solve(challenge, *, debug=False, capture=None):
        assert challenge.candidates == ["dog", "cat"]
        assert capture is not None
        assert capture.output_dir == str(tmp_path / "captures")
        assert capture.verdict == "reject_antibot"
        return SolveResult(
            success=False,
            status="uncertain",
            error_code="LOW_CONFIDENCE",
            error_message="no match",
            capture={"challenge_id": "cli-1", "record_path": "x", "index_path": "y"},
        )

    monkeypatch.setattr("antibot_image_solver.cli.solve_challenge", fake_solve)

    exit_code = main(
        [
            "solve-image",
            "--image",
            str(image_path),
            "--candidates",
            "dog,cat",
            "--json",
            "--capture-dir",
            str(tmp_path / "captures"),
            "--capture-verdict",
            "reject_antibot",
            "--capture-challenge-id",
            "cli-1",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["capture"]["challenge_id"] == "cli-1"
