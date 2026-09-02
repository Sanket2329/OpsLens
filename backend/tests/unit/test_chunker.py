"""
Unit tests for the Chunker service.
"""

import pytest

from app.services.chunker import Chunker


class TestChunker:
    def setup_method(self):
        self.chunker = Chunker()

    def test_returns_list(self):
        chunks = self.chunker.split("Hello world.")
        assert isinstance(chunks, list)

    def test_non_empty_input_produces_chunks(self):
        text = "This is a sentence. " * 50
        chunks = self.chunker.split(text)
        assert len(chunks) > 0

    def test_all_chunks_are_strings(self):
        text = "Word " * 200
        chunks = self.chunker.split(text)
        assert all(isinstance(c, str) for c in chunks)

    def test_chunks_respect_max_size(self):
        text = "word " * 500  # well over chunk_size
        chunks = self.chunker.split(text)
        # With overlap the max observed size may slightly exceed chunk_size
        # but no chunk should be wildly larger
        for chunk in chunks:
            assert len(chunk) <= 1700, f"Chunk too large: {len(chunk)}"

    def test_empty_string_returns_empty_list(self):
        chunks = self.chunker.split("")
        assert chunks == [] or all(c.strip() == "" for c in chunks)

    def test_short_text_single_chunk(self):
        text = "Short document."
        chunks = self.chunker.split(text)
        assert len(chunks) == 1
        assert "Short document" in chunks[0]

    def test_content_preserved(self):
        text = "Alpha. " * 30 + "Unique marker word. " + "Beta. " * 30
        chunks = self.chunker.split(text)
        combined = " ".join(chunks)
        assert "Unique marker word" in combined
