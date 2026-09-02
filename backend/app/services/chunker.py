"""
Chunker — splits extracted text into overlapping chunks for embedding.

Chunk size tuning:
  - chunk_size=1500 chars ≈ ~250 words ≈ meaningful semantic unit
  - chunk_overlap=200 chars ensures continuity across chunk boundaries
  - Smaller chunks (500) create too many API calls and hit quota faster
  - Larger chunks (3000+) lose semantic precision in retrieval

For a 200-page PDF (~200k chars):
  chunk_size=1500 → ~150 chunks → 2 API calls (batch_size=100)
  chunk_size=500  → ~450 chunks → 5 API calls  (was causing quota exhaustion)
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter


class Chunker:

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=200,
            separators=[
                "\n\n",
                "\n",
                ". ",
                "! ",
                "? ",
                " ",
                "",
            ],
        )

    def split(self, text: str) -> list[str]:
        return self.splitter.split_text(text)
