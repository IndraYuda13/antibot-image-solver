from __future__ import annotations

import subprocess

from PIL import Image

from antibot_image_solver import ocr


def test_ocr_file_cache_reuses_candidates(monkeypatch, tmp_path):
    image_path = tmp_path / "tiny.png"
    Image.new("RGB", (2, 2), "white").save(image_path)
    png_bytes = image_path.read_bytes()
    calls = []

    monkeypatch.setattr(ocr, "ensure_tesseract_available", lambda: "/usr/bin/tesseract")
    monkeypatch.setattr(ocr, "pil_variants", lambda payload, profile=None: [payload])
    monkeypatch.setenv("ANTIBOT_OCR_CACHE_DIR", str(tmp_path / "ocr-cache"))

    def fake_check_output(command, *, stderr=None, text=None, timeout=None):
        calls.append(command)
        return "cat\n"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    assert ocr.ocr_candidates_from_bytes(png_bytes, profile="turbo") == ["cat"]
    assert ocr.ocr_candidates_from_bytes(png_bytes, profile="turbo") == ["cat"]
    assert len(calls) == 2  # turbo profile has psm 7 and 8 only on first uncached call
