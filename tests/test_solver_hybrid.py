from __future__ import annotations

from antibot_image_solver.models import AntibotChallenge, OptionImage
from antibot_image_solver.solver import get_full_fallback_min_gain, get_low_confidence_threshold, solve_challenge


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



def test_low_confidence_threshold_defaults_and_clamps(monkeypatch):
    monkeypatch.delenv("ANTIBOT_LOW_CONFIDENCE_THRESHOLD", raising=False)
    assert get_low_confidence_threshold() == 0.50
    monkeypatch.setenv("ANTIBOT_LOW_CONFIDENCE_THRESHOLD", "bad")
    assert get_low_confidence_threshold() == 0.50
    monkeypatch.setenv("ANTIBOT_LOW_CONFIDENCE_THRESHOLD", "2")
    assert get_low_confidence_threshold() == 0.99
    monkeypatch.setenv("ANTIBOT_LOW_CONFIDENCE_THRESHOLD", "-1")
    assert get_low_confidence_threshold() == 0.0


def test_full_fallback_min_gain_defaults_and_clamps(monkeypatch):
    monkeypatch.delenv("ANTIBOT_FULL_FALLBACK_MIN_GAIN", raising=False)
    assert get_full_fallback_min_gain() == 0.08
    monkeypatch.setenv("ANTIBOT_FULL_FALLBACK_MIN_GAIN", "bad")
    assert get_full_fallback_min_gain() == 0.08
    monkeypatch.setenv("ANTIBOT_FULL_FALLBACK_MIN_GAIN", "2")
    assert get_full_fallback_min_gain() == 0.50
    monkeypatch.setenv("ANTIBOT_FULL_FALLBACK_MIN_GAIN", "-1")
    assert get_full_fallback_min_gain() == 0.0


def test_fast_profile_uses_full_fallback_when_confidence_improves(monkeypatch):
    calls = []

    def fake_ocr(image_base64: str, *, language=None, profile=None):
        calls.append((image_base64, profile))
        data = {
            "turbo": {
                "instruction": ["xxx yyy zzz"],
                "image-a": ["Tea"],
                "image-b": ["Pie"],
                "image-c": ["Cup"],
            },
            "fast": {
                "instruction": ["tea cup pie"],
                "image-a": ["Tea"],
                "image-b": ["Pie"],
                "image-c": ["Cup"],
            },
            "full": {
                "instruction": ["tea pie cup"],
                "image-a": ["Tea"],
                "image-b": ["Pie"],
                "image-c": ["Cup"],
            },
        }
        return data[profile][image_base64]

    monkeypatch.setenv("ANTIBOT_OCR_PROFILE", "fast")
    monkeypatch.setenv("ANTIBOT_LOW_CONFIDENCE_THRESHOLD", "0.99")
    monkeypatch.setenv("ANTIBOT_FULL_FALLBACK_MIN_GAIN", "0")
    monkeypatch.setattr("antibot_image_solver.solver.ocr_candidates_from_base64", fake_ocr)

    result = solve_challenge(_challenge())

    assert result.ordered_ids == ["a", "b", "c"]
    assert "full" in {profile for _, profile in calls}
    assert result.meta["ocr_profile"] == "full"
    assert result.meta["fallback_profile"] == "full"
    assert result.meta["fallback_reason"] == "low_confidence"
    assert result.meta["fallback_from_profile"] == "fast"


def test_fast_profile_keeps_fast_result_when_full_fallback_does_not_improve(monkeypatch):
    calls = []

    def fake_ocr(image_base64: str, *, language=None, profile=None):
        calls.append((image_base64, profile))
        data = {
            "turbo": {
                "instruction": ["xxx yyy zzz"],
                "image-a": ["Tea"],
                "image-b": ["Pie"],
                "image-c": ["Cup"],
            },
            "fast": {
                "instruction": ["tea pie cup"],
                "image-a": ["Tea"],
                "image-b": ["Pie"],
                "image-c": ["Cup"],
            },
            "full": {
                "instruction": ["tea cup pie"],
                "image-a": ["Tea"],
                "image-b": ["Pie"],
                "image-c": ["Cup"],
            },
        }
        return data[profile][image_base64]

    monkeypatch.setenv("ANTIBOT_OCR_PROFILE", "fast")
    monkeypatch.setenv("ANTIBOT_LOW_CONFIDENCE_THRESHOLD", "0.99")
    monkeypatch.setenv("ANTIBOT_FULL_FALLBACK_MIN_GAIN", "0.50")
    monkeypatch.setattr("antibot_image_solver.solver.ocr_candidates_from_base64", fake_ocr)

    result = solve_challenge(_challenge())

    assert result.ordered_ids == ["a", "b", "c"]
    assert "full" in {profile for _, profile in calls}
    assert result.meta["ocr_profile"] == "fast"
    assert result.meta["fallback_reason"] == "low_confidence_not_improved"
    assert result.meta["fallback_candidate_success"] is True
