from __future__ import annotations

import subprocess

from PIL import Image

from antibot_image_solver import ocr


def test_ocr_subprocess_timeout_is_passed_and_skipped(monkeypatch, tmp_path):
    image_path = tmp_path / "tiny.png"
    Image.new("RGB", (2, 2), "white").save(image_path)
    png_bytes = image_path.read_bytes()
    seen_timeouts = []

    monkeypatch.setattr(ocr, "ensure_tesseract_available", lambda: "/usr/bin/tesseract")
    monkeypatch.setattr(ocr, "pil_variants", lambda payload, profile=None: [payload])
    monkeypatch.setenv("ANTIBOT_OCR_TIMEOUT_SECONDS", "1.25")

    def fake_check_output(command, *, stderr=None, text=None, timeout=None):
        seen_timeouts.append(timeout)
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    assert ocr.ocr_candidates_from_bytes(png_bytes, profile="turbo") == []
    assert seen_timeouts == [1.25, 1.25]
