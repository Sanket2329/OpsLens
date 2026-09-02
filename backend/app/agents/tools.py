"""
Custom CrewAI tools for OpsLens agents.

Each tool wraps existing OpsLens services so agents can
interact with the knowledge base without duplicating logic.
"""

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore


# ---------------------------------------------------------------------------
# Input schemas (required by CrewAI tool framework)
# ---------------------------------------------------------------------------

class VectorSearchInput(BaseModel):
    query: str = Field(description="The search query to find relevant documentation")
    limit: int = Field(default=6, description="Max number of chunks to return")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class VectorSearchTool(BaseTool):
    """
    Semantic search over the organisation's indexed knowledge base.

    The agent provides a natural-language query and receives the most
    relevant document chunks with similarity scores and citations.
    """

    name: str = "knowledge_base_search"
    description: str = (
        "Search the organisation's knowledge base (runbooks, architecture docs, "
        "previous incidents) for information relevant to the current incident. "
        "Returns ranked document chunks with source citations and similarity scores. "
        "Use this to ground your analysis in real documentation."
    )
    args_schema: Type[BaseModel] = VectorSearchInput

    # These are injected after construction — not Pydantic fields
    _organization_id: int = 0
    _embedder: EmbeddingService = None
    _store: VectorStore = None

    def __init__(self, organization_id: int, **kwargs):
        super().__init__(**kwargs)
        # Use object.__setattr__ to bypass Pydantic validation for private attrs
        object.__setattr__(self, "_organization_id", organization_id)
        object.__setattr__(self, "_embedder", EmbeddingService())
        object.__setattr__(self, "_store", VectorStore())

    def _run(self, query: str, limit: int = 6) -> str:
        embedder = object.__getattribute__(self, "_embedder")
        store = object.__getattribute__(self, "_store")
        org_id = object.__getattribute__(self, "_organization_id")

        query_vector = embedder.embed(query)
        results = store.search(
            query_vector=query_vector,
            organization_id=org_id,
            limit=limit,
        )

        if not results:
            return "No relevant documentation found in the knowledge base."

        lines = []
        for i, point in enumerate(results, 1):
            payload = point.payload
            score = round(point.score, 4) if point.score else 0.0
            filename = payload.get("filename", f"doc_{payload.get('document_id')}")
            chunk_idx = payload.get("chunk_index", "?")
            text = payload.get("text", "")[:400]
            lines.append(
                f"[{i}] {filename} | Chunk #{chunk_idx} | Similarity: {score}\n"
                f'    "{text}{"..." if len(payload.get("text", "")) > 400 else ""}"'
            )

        return "\n\n".join(lines)
