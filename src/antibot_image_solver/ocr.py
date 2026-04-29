from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps


def get_ocr_cache_dir() -> Path | None:
    raw = os.getenv("ANTIBOT_OCR_CACHE_DIR", "").strip()
    if not raw:
        return None
    return Path(raw)


def _ocr_cache_key(png_bytes: bytes, *, language: Optional[str], profile: str) -> str:
    digest = hashlib.sha256()
    digest.update(b"antibot-ocr-cache-v1\0")
    digest.update(profile.encode())
    digest.update(b"\0")
    digest.update((language or "").encode())
    digest.update(b"\0")
    digest.update(png_bytes)
    return digest.hexdigest()


def _read_ocr_cache(png_bytes: bytes, *, language: Optional[str], profile: str) -> list[str] | None:
    cache_dir = get_ocr_cache_dir()
    if cache_dir is None:
        return None
    path = cache_dir / f"{_ocr_cache_key(png_bytes, language=language, profile=profile)}.json"
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("profile") != profile or payload.get("language") != (language or ""):
        return None
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return None
    return [str(item) for item in candidates]


def _write_ocr_cache(png_bytes: bytes, *, language: Optional[str], profile: str, candidates: list[str]) -> None:
    cache_dir = get_ocr_cache_dir()
    if cache_dir is None:
        return
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / f"{_ocr_cache_key(png_bytes, language=language, profile=profile)}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"profile": profile, "language": language or "", "candidates": candidates}, ensure_ascii=False))
        tmp.replace(path)
    except OSError:
        return


class OcrRuntimeError(RuntimeError):
    pass


def get_ocr_profile() -> str:
    profile = os.getenv("ANTIBOT_OCR_PROFILE", "full").strip().lower()
    return profile if profile in {"full", "fast", "turbo"} else "full"


def get_ocr_timeout_seconds() -> float:
    raw = os.getenv("ANTIBOT_OCR_TIMEOUT_SECONDS", "3.0").strip()
    try:
        value = float(raw)
    except ValueError:
        return 3.0
    return max(0.25, value)


def ensure_tesseract_available() -> str:
    path = shutil.which("tesseract")
    if not path:
        raise OcrRuntimeError("tesseract binary not found in PATH")
    return path


def pil_variants(png_bytes: bytes, *, profile: Optional[str] = None) -> list[bytes]:
    selected_profile = (profile or get_ocr_profile()).strip().lower()
    variants = [] if selected_profile == "turbo" else [png_bytes]
    try:
        image = Image.open(io.BytesIO(png_bytes)).convert("L")
        prepared = [image]
        thresholds = (110, 150) if selected_profile == "full" else (130,)
        scales = (6, 8, 10) if selected_profile == "full" else (8,)
        for threshold in thresholds:
            bw = image.point(lambda value, thr=threshold: 255 if value > thr else 0)
            prepared.append(bw)
            if selected_profile != "turbo":
                prepared.append(ImageOps.invert(bw))
        seen: set[bytes] = set()
        for base_image in prepared:
            for scale in scales:
                resized = base_image.resize(
                    (base_image.width * scale, base_image.height * scale),
                    Image.Resampling.NEAREST,
                )
                buffer = io.BytesIO()
                resized.save(buffer, format="PNG")
                payload = buffer.getvalue()
                if payload not in seen:
                    seen.add(payload)
                    variants.append(payload)
    except Exception:
        pass
    return variants


def ocr_candidates_from_bytes(png_bytes: bytes, *, language: Optional[str] = None, profile: Optional[str] = None) -> list[str]:
    ensure_tesseract_available()
    selected_profile = (profile or get_ocr_profile()).strip().lower()
    if selected_profile not in {"full", "fast", "turbo"}:
        selected_profile = "full"
    cached = _read_ocr_cache(png_bytes, language=language, profile=selected_profile)
    if cached is not None:
        return cached
    psm_modes = (6, 7, 8, 10, 13) if selected_profile == "full" else ((7, 8) if selected_profile == "turbo" else (7, 8, 13))
    timeout_seconds = get_ocr_timeout_seconds()
    results: list[str] = []
    seen: set[str] = set()
    for data in pil_variants(png_bytes, profile=selected_profile):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            for psm in psm_modes:
                command = ["tesseract", tmp_path, "stdout", "--psm", str(psm)]
                if language:
                    command += ["-l", language]
                try:
                    output = subprocess.check_output(
                        command,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        timeout=timeout_seconds,
                    )
                except Exception:
                    continue
                text = output.replace("\f", "").strip()
                if text and text not in seen:
                    seen.add(text)
                    results.append(text)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    _write_ocr_cache(png_bytes, language=language, profile=selected_profile, candidates=results)
    return results


def ocr_candidates_from_base64(image_base64: str, *, language: Optional[str] = None, profile: Optional[str] = None) -> list[str]:
    try:
        png_bytes = base64.b64decode(image_base64)
    except Exception as exc:
        raise OcrRuntimeError(f"invalid base64 image payload: {exc}") from exc
    return ocr_candidates_from_bytes(png_bytes, language=language, profile=profile)
