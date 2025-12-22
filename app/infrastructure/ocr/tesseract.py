from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from PIL import Image

from app.infrastructure.ocr.base import OcrEngine


class TesseractOcrEngine(OcrEngine):
    def __init__(self, language: str = "ara+eng") -> None:
        self.language = language

    def extract_text(self, images: Sequence["Image.Image"]) -> str:
        import pytesseract
        from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

        chunks: list[str] = []
        psm_modes = (6, 4, 11)
        for image in images:
            processed = _preprocess_image(
                image,
                Image=Image,
                ImageChops=ImageChops,
                ImageEnhance=ImageEnhance,
                ImageFilter=ImageFilter,
                ImageOps=ImageOps,
            )
            text = _ocr_with_psm(processed, pytesseract, self.language, psm_modes)
            if text:
                chunks.append(text)
        return "\n".join(chunks)


def _ocr_with_psm(image, pytesseract, language: str, psm_modes: Sequence[int]) -> str:
    best_text = ""
    for psm in psm_modes:
        config = f"--oem 1 --psm {psm}"
        candidate = pytesseract.image_to_string(image, lang=language, config=config).strip()
        if len(candidate) > len(best_text):
            best_text = candidate
        if len(best_text) >= 80:
            break
    return best_text


def _preprocess_image(image, Image, ImageChops, ImageEnhance, ImageFilter, ImageOps):
    image = image.convert("RGB")
    width, height = image.size
    scale = 3 if max(width, height) < 900 else 2
    image = image.resize((width * scale, height * scale), resample=Image.LANCZOS)
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    contrast = ImageEnhance.Contrast(gray).enhance(1.8)
    return _adaptive_threshold(contrast, ImageChops, ImageFilter, ImageOps)


def _adaptive_threshold(image, ImageChops, ImageFilter, ImageOps):
    blurred = image.filter(ImageFilter.GaussianBlur(radius=3))
    diff = ImageChops.subtract(image, blurred)
    diff = ImageOps.autocontrast(diff)
    return diff.point(lambda value: 255 if value > 20 else 0)
