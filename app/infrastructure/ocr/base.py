from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from PIL import Image


class OcrEngine(ABC):
    @abstractmethod
    def extract_text(self, images: Sequence["Image.Image"]) -> str:
        raise NotImplementedError
