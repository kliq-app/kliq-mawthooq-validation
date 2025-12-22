from __future__ import annotations

import io
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from PIL import Image


class PdfRenderer:
    def __init__(self, zoom: float = 2.0) -> None:
        self.zoom = zoom

    def render_pages(self, data: bytes, max_pages: int = 2) -> List["Image.Image"]:
        from PIL import Image

        images: List[Image.Image] = []
        import fitz

        with fitz.open(stream=data, filetype="pdf") as document:
            page_count = min(max_pages, document.page_count)
            matrix = fitz.Matrix(self.zoom, self.zoom)
            for index in range(page_count):
                page = document.load_page(index)
                pix = page.get_pixmap(matrix=matrix)
                image_bytes = pix.tobytes("png")
                image = Image.open(io.BytesIO(image_bytes))
                images.append(image.convert("RGB"))
        return images
