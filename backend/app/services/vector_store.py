import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class VectorStore:

    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url)
        self.collection_name = settings.qdrant_collection

    def create_collection(self) -> None:
        """Idempotently create the Qdrant collection at startup."""
        collections = self.client.get_collections().collections
        names = [c.name for c in collections]

        if self.collection_name not in names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.qdrant_vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "Qdrant collection created: name=%s vector_size=%d",
                self.collection_name,
                settings.qdrant_vector_size,
            )
        else:
            logger.debug("Qdrant collection already exists: %s", self.collection_name)

    def store_chunks(
        self,
        document_id: int,
        filename: str,
        organization_id: int,
        chunks: list[str],
        embeddings: list[list[float]],
        start_index: int = 0,
    ) -> None:
        """
        Upsert document chunks with org-scoped metadata.

        Args:
            start_index: The chunk_index of the first item in chunks/embeddings.
                         Used for resume support — chunks at index N get
                         chunk_index=N so re-upserts are idempotent.
        """
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "document_id": document_id,
                    "filename": filename,
                    "organization_id": organization_id,
                    "chunk_index": start_index + index,
                    "text": chunk,
                },
            )
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        logger.info(
            "Stored %d chunks (idx %d-%d): document_id=%d org_id=%d",
            len(points),
            start_index,
            start_index + len(points) - 1,
            document_id,
            organization_id,
        )

    def count_document_chunks(self, document_id: int) -> int:
        """Return how many chunks are stored for a given document_id."""
        result = self.client.count(
            collection_name=self.collection_name,
            count_filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
            exact=True,
        )
        return result.count

    def delete_by_document(self, document_id: int) -> None:
        """Remove all Qdrant points that belong to a given document_id."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )
        logger.info("Deleted Qdrant vectors for document_id=%d", document_id)

    def search(
        self,
        query_vector: list[float],
        organization_id: int | None = None,
        limit: int = 5,
    ) -> list:
        """
        Semantic search, optionally scoped to an organization.
        Returns ScoredPoint objects; callers access .payload and .score.
        """
        query_filter = None

        if organization_id is not None:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="organization_id",
                        match=MatchValue(value=organization_id),
                    )
                ]
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        logger.debug(
            "Vector search: org_id=%s limit=%d hits=%d",
            organization_id,
            limit,
            len(results.points),
        )

        return results.points
