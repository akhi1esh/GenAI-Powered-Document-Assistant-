"""PDF text extraction with light cleanup."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class ExtractedDoc:
    path: str
    text: str
    n_pages: int

    @property
    def is_empty(self) -> bool:
        return len(self.text.strip()) < 20


def _clean(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"-\n(?=[a-z])", "", text)      # de-hyphenate line wraps
    text = re.sub(r"[ \t]+", " ", text)           # collapse spaces
    text = re.sub(r"\n{3,}", "\n\n", text)        # collapse blank lines
    return text.strip()


def extract_pdf_text(path: str | Path) -> ExtractedDoc:
    """Extract text from every page of a PDF.

    Raises ValueError for scanned/image-only PDFs (no text layer); those need OCR.
    """
    path = Path(path)
    reader = PdfReader(str(path))
    pages = [(p.extract_text() or "") for p in reader.pages]
    doc = ExtractedDoc(str(path), _clean("\n\n".join(pages)), len(pages))
    if doc.is_empty:
        raise ValueError(f"No extractable text in {path.name}; it may be a scanned PDF (OCR needed).")
    return doc
