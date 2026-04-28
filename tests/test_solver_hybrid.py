from __future__ import annotations

from antibot_image_solver.models import AntibotChallenge, OptionImage
from antibot_image_solver.solver import solve_challenge


def _challenge() -> AntibotChallenge:
    return AntibotChallenge(
        instruction_image_base64="instruction",
        options=[
            OptionImage(id="a", image_base64="image-a"),
            OptionImage(id="b", image_base64="image-b"),
            OptionImage(id="c", image_base64="image-c"),
        ],
        domain_hint="claimcoin",
    )


def test_fast_profile_accepts_high_confidence_turbo_stage(monkeypatch):
    calls = []

    def fake_ocr(image_base64: str, *, language=None, profile=None):
        calls.append((image_base64, profile))
        mapping = {
            "instruction": ["dog cat mouse"],
            "image-a": ["dog"],
            "image-b": ["cat"],
            "image-c": ["mouse"],
        }
        return mapping[image_base64]

    monkeypatch.setenv("ANTIBOT_OCR_PROFILE", "fast")
    monkeypatch.setattr("antibot_image_solver.solver.ocr_candidates_from_base64", fake_ocr)

    result = solve_challenge(_challenge())

    assert result.ordered_ids == ["a", "b", "c"]
    assert {profile for _, profile in calls} == {"turbo"}


def test_fast_profile_falls_back_when_turbo_confidence_is_low(monkeypatch):
    calls = []

    def fake_ocr(image_base64: str, *, language=None, profile=None):
        calls.append((image_base64, profile))
        turbo = {
            "instruction": ["xxx yyy zzz"],
            "image-a": ["Tea"],
            "image-b": ["Binary"],
            "image-c": ["Money"],
        }
        fast = {
            "instruction": ["Tea Binary Money"],
            "image-a": ["Tea"],
            "image-b": ["Binary"],
            "image-c": ["Money"],
        }
        return (turbo if profile == "turbo" else fast)[image_base64]

    monkeypatch.setenv("ANTIBOT_OCR_PROFILE", "fast")
    monkeypatch.setattr("antibot_image_solver.solver.ocr_candidates_from_base64", fake_ocr)

    result = solve_challenge(_challenge())

    assert result.ordered_ids == ["a", "b", "c"]
    assert "turbo" in {profile for _, profile in calls}
    assert "fast" in {profile for _, profile in calls}
