from __future__ import annotations

import logging
import shutil
import subprocess
from functools import lru_cache

from app.shared.settings import settings

logger = logging.getLogger("app.deps")


@lru_cache
def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


@lru_cache
def tesseract_languages() -> list[str]:
    if not tesseract_available():
        return []
    try:
        result = subprocess.run(
            ["tesseract", "--list-langs"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return []

    lines = result.stdout.splitlines()
    langs: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.lower().startswith("list of available languages"):
            continue
        langs.append(line)
    return langs


def tesseract_has_ara() -> bool:
    return "ara" in tesseract_languages()


@lru_cache
def pdftoppm_available() -> bool:
    return shutil.which("pdftoppm") is not None


def log_dependency_status() -> None:
    if settings.ocr_enabled:
        logger.info(
            "tesseract.status",
            extra={
                "available": tesseract_available(),
                "ara_installed": tesseract_has_ara(),
            },
        )
    logger.info(
        "pdftoppm.status",
        extra={
            "available": pdftoppm_available(),
            "note": "used by pdf2image when enabled",
        },
    )
