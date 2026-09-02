"""
DocumentProcessor — extracts raw text from uploaded files.

Supported formats: PDF, TXT, MD
Logs page count and character count for observability.
"""

import os

from pypdf import PdfReader

from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentProcessor:

    def extract_text(self, file_path: str) -> str:
        extension = os.path.splitext(file_path)[1].lower()

        if extension == ".pdf":
            return self._extract_pdf(file_path)
        if extension == ".txt":
            return self._extract_txt(file_path)
        if extension == ".md":
            return self._extract_md(file_path)

        raise ValueError(
            f"Unsupported file type '{extension}'. Supported: .pdf, .txt, .md"
        )

    def _extract_pdf(self, file_path: str) -> str:
        reader = PdfReader(file_path)
        page_count = len(reader.pages)
        logger.info("PDF: %s | Pages: %d", os.path.basename(file_path), page_count)

        text_parts: list[str] = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
            else:
                logger.debug("Page %d/%d has no extractable text", i + 1, page_count)

        text = "\n".join(text_parts)
        logger.info(
            "PDF extracted: %d pages → %d characters",
            page_count,
            len(text),
        )
        return text

    def _extract_txt(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        logger.info(
            "TXT extracted: %s → %d characters",
            os.path.basename(file_path),
            len(text),
        )
        return text

    def _extract_md(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        logger.info(
            "MD extracted: %s → %d characters",
            os.path.basename(file_path),
            len(text),
        )
        return text
