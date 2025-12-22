from __future__ import annotations

import io


class PdfTextExtractor:
    def extract(self, data: bytes) -> str:
        from pdfminer.high_level import extract_text

        with io.BytesIO(data) as buffer:
            return extract_text(buffer)
