from __future__ import annotations

import base64
import io
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from PIL import Image, ImageOps


class OcrRuntimeError(RuntimeError):
    pass


def ensure_tesseract_available() -> str:
    path = shutil.which("tesseract")
    if not path:
        raise OcrRuntimeError("tesseract binary not found in PATH")
    return path


def pil_variants(png_bytes: bytes) -> list[bytes]:
    variants = [png_bytes]
    try:
        image = Image.open(io.BytesIO(png_bytes)).convert("L")
        prepared = [image]
        for threshold in (110, 150):
            bw = image.point(lambda value, thr=threshold: 255 if value > thr else 0)
            prepared.append(bw)
            prepared.append(ImageOps.invert(bw))
        seen: set[bytes] = set()
        for base_image in prepared:
            for scale in (6, 8, 10):
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


def ocr_candidates_from_bytes(png_bytes: bytes, *, language: Optional[str] = None) -> list[str]:
    ensure_tesseract_available()
    results: list[str] = []
    seen: set[str] = set()
    for data in pil_variants(png_bytes):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            for psm in (6, 7, 8, 10, 13):
                command = ["tesseract", tmp_path, "stdout", "--psm", str(psm)]
                if language:
                    command += ["-l", language]
                try:
                    output = subprocess.check_output(
                        command,
                        stderr=subprocess.DEVNULL,
                        text=True,
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
    return results


def ocr_candidates_from_base64(image_base64: str, *, language: Optional[str] = None) -> list[str]:
    try:
        png_bytes = base64.b64decode(image_base64)
    except Exception as exc:
        raise OcrRuntimeError(f"invalid base64 image payload: {exc}") from exc
    return ocr_candidates_from_bytes(png_bytes, language=language)
