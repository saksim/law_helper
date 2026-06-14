from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional runtime dependency
    Image = None

try:
    import pypdfium2 as pdfium
except Exception:  # pragma: no cover - optional runtime dependency
    pdfium = None


@dataclass
class OcrPage:
    page_no: int
    text: str
    bbox: list[float]
    status: str
    provider: str
    detail: str | None = None


@dataclass
class OcrResult:
    pages: list[OcrPage]
    status: str
    provider: str
    detail: str | None = None


class OCRService:
    def __init__(self) -> None:
        self.provider = os.getenv("LAW_PLATFORM_OCR_PROVIDER", "tesseract").strip().lower()
        self.tesseract_cmd = os.getenv("LAW_PLATFORM_TESSERACT_CMD") or shutil.which("tesseract")
        self.language = os.getenv("LAW_PLATFORM_OCR_LANG", "chi_sim+eng")
        self.timeout_seconds = int(os.getenv("LAW_PLATFORM_OCR_TIMEOUT_SECONDS", "30"))

    def extract_pages(self, filename: str, content: bytes) -> OcrResult:
        if self.provider in {"", "none", "disabled"}:
            return OcrResult([], "configuration_required", self.provider or "disabled", "OCR provider is disabled.")
        if self.provider != "tesseract":
            return OcrResult([], "configuration_required", self.provider, "Only tesseract provider is wired in this P0 runtime.")
        if not self.tesseract_cmd:
            return OcrResult([], "configuration_required", "tesseract", "Tesseract executable is not configured.")

        images = self._images_from_file(filename, content)
        if not images:
            return OcrResult([], "unsupported_input", "tesseract", "No renderable image pages were found.")

        pages: list[OcrPage] = []
        for page_no, image in images:
            try:
                text = self._run_tesseract(image)
                status = "done" if text.strip() else "empty"
                detail = None if text.strip() else "OCR returned empty text."
            except Exception as exc:  # pragma: no cover - depends on local OCR binary
                text = ""
                status = "failed"
                detail = str(exc)
            width, height = image.size
            pages.append(OcrPage(page_no, text, [0, 0, float(width), float(height)], status, "tesseract", detail))
        overall = "done" if any(page.text.strip() for page in pages) else "failed"
        return OcrResult(pages, overall, "tesseract", None)

    def _images_from_file(self, filename: str, content: bytes) -> list[tuple[int, Any]]:
        lowered = filename.lower()
        if lowered.endswith(".pdf"):
            return self._images_from_pdf(content)
        return self._images_from_image(content)

    def _images_from_pdf(self, content: bytes) -> list[tuple[int, Any]]:
        if pdfium is None or Image is None:
            return []
        document = pdfium.PdfDocument(content)
        images = []
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=2)
            images.append((index + 1, bitmap.to_pil()))
        return images

    def _images_from_image(self, content: bytes) -> list[tuple[int, Any]]:
        if Image is None:
            return []
        image = Image.open(BytesIO(content))
        return [(1, image.convert("RGB"))]

    def _run_tesseract(self, image: Any) -> str:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
        try:
            image.save(temp_path)
            completed = subprocess.run(
                [self.tesseract_cmd, temp_path, "stdout", "-l", self.language],
                check=False,
                capture_output=True,
                timeout=self.timeout_seconds,
            )
            if completed.returncode != 0:
                error = completed.stderr.decode("utf-8", errors="replace")
                raise RuntimeError(error.strip() or f"tesseract exited with {completed.returncode}")
            return completed.stdout.decode("utf-8", errors="replace")
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass