"""
EmbeddingService — generates Gemini embeddings with production-grade reliability.

Features:
  embed()       — single text embedding with retry
  embed_batch() — batch embedding (up to 100 per API call) with retry + progress
  
Retry policy:
  - 429 RESOURCE_EXHAUSTED → exponential backoff with full jitter, up to 5 retries
  - 5xx server errors → same backoff
  - Transient network errors → same backoff
  - Non-retryable 4xx → raise immediately

Backoff schedule (with jitter):
  Attempt 1: 0 – 2s
  Attempt 2: 0 – 4s
  Attempt 3: 0 – 8s
  Attempt 4: 0 – 16s
  Attempt 5: 0 – 32s  (capped at 60s)
"""

import math
import random
import time
from collections.abc import Iterator

from google import genai

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Gemini embedding API: max texts per batch request
_BATCH_SIZE = 100

# Retry configuration
_MAX_RETRIES = 8
_BASE_DELAY_S = 1.0
_MAX_DELAY_S = 90.0   # allow up to 90s for quota resets


def _is_rate_limit(exc: Exception) -> bool:
    """Detect 429 / RESOURCE_EXHAUSTED across all error shapes the SDK may raise."""
    msg = str(exc).lower()
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return (
        code == 429
        or "429" in msg
        or "resource_exhausted" in msg
        or "quota" in msg
        or "rate limit" in msg
    )


def _is_retryable(exc: Exception) -> bool:
    """Return True for 429s, 5xx errors, and transient network failures."""
    if _is_rate_limit(exc):
        return True
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(code, int) and code >= 500:
        return True
    msg = str(exc).lower()
    return any(k in msg for k in ("timeout", "connection", "reset", "unavailable", "503", "500"))


def _get_retry_delay_from_error(exc: Exception) -> float | None:
    """
    Extract the suggested retry delay from a Gemini 429 error response.
    The API includes 'retryDelay' in the error details — honor it.
    """
    try:
        msg = str(exc)
        import re
        # Match patterns like "Please retry in 15.43s" or "retryDelay: 15s"
        match = re.search(r"retry[^\d]*(\d+(?:\.\d+)?)\s*s", msg, re.IGNORECASE)
        if match:
            return min(float(match.group(1)) + 2.0, _MAX_DELAY_S)  # add 2s buffer
    except Exception:
        pass
    return None


def _backoff(attempt: int, exc: Exception | None = None) -> float:
    """
    Full-jitter exponential backoff.
    If the error includes a Gemini-suggested retry delay, honor it.
    """
    if exc is not None and _is_rate_limit(exc):
        suggested = _get_retry_delay_from_error(exc)
        if suggested:
            # Add jitter on top of the suggested delay
            return suggested + random.uniform(0, 3.0)

    ceiling = min(_BASE_DELAY_S * (2 ** attempt), _MAX_DELAY_S)
    return random.uniform(0, ceiling)


def _with_retry(fn, *args, **kwargs):
    """
    Execute fn(*args, **kwargs) with exponential backoff.
    Raises on non-retryable errors or after all retries exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if _is_retryable(exc):
                delay = _backoff(attempt, exc)
                if _is_rate_limit(exc):
                    logger.warning(
                        "429 RESOURCE_EXHAUSTED (attempt %d/%d). "
                        "Retrying in %.1fs…",
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                    )
                else:
                    logger.warning(
                        "Transient error (attempt %d/%d): %s. Retrying in %.1fs…",
                        attempt + 1,
                        _MAX_RETRIES,
                        type(exc).__name__,
                        delay,
                    )
                time.sleep(delay)
            else:
                # Non-retryable — fail fast
                raise

    raise RuntimeError(
        f"Embedding failed after {_MAX_RETRIES} retries. Last error: {last_exc}"
    ) from last_exc


class EmbeddingService:

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_embedding_model

    # ------------------------------------------------------------------
    # Single text embedding
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Embed a single text string. Used for query embedding."""
        start = time.monotonic()

        response = _with_retry(
            self.client.models.embed_content,
            model=self.model,
            contents=text,
        )

        vector = response.embeddings[0].values
        logger.debug(
            "Embedded query: model=%s dim=%d elapsed=%.2fs",
            self.model,
            len(vector),
            round(time.monotonic() - start, 2),
        )
        return vector

    # ------------------------------------------------------------------
    # Batch embedding
    # ------------------------------------------------------------------

    def embed_batch(
        self,
        texts: list[str],
        on_progress: "((completed: int, total: int) -> None) | None" = None,
    ) -> list[list[float]]:
        """
        Embed a list of texts using batched Gemini API calls.

        Sends up to _BATCH_SIZE texts per API call instead of one call per text.
        For a 300-chunk document: 3 API calls instead of 300.

        Args:
            texts: List of strings to embed.
            on_progress: Optional callback(chunks_completed, chunks_total)
                         called after each batch completes.

        Returns:
            List of embedding vectors in the same order as texts.

        Raises:
            RuntimeError: If any batch fails after all retries.
        """
        if not texts:
            return []

        total = len(texts)
        n_batches = math.ceil(total / _BATCH_SIZE)
        all_vectors: list[list[float]] = []
        completed = 0

        logger.info(
            "Batch embedding: %d chunks → %d batches (batch_size=%d) model=%s",
            total,
            n_batches,
            _BATCH_SIZE,
            self.model,
        )

        for batch_num, batch_texts in enumerate(_batched(texts, _BATCH_SIZE), 1):
            batch_start = time.monotonic()

            logger.info(
                "Embedding batch %d/%d (%d chunks)…",
                batch_num,
                n_batches,
                len(batch_texts),
            )

            response = _with_retry(
                self.client.models.embed_content,
                model=self.model,
                contents=batch_texts,
            )

            vectors = [e.values for e in response.embeddings]

            # Sanity check: response must have same count as input
            if len(vectors) != len(batch_texts):
                raise ValueError(
                    f"Gemini returned {len(vectors)} embeddings for {len(batch_texts)} inputs "
                    f"in batch {batch_num}/{n_batches}"
                )

            all_vectors.extend(vectors)
            completed += len(batch_texts)

            logger.info(
                "Batch %d/%d done: %d/%d chunks embedded (%.1fs)",
                batch_num,
                n_batches,
                completed,
                total,
                round(time.monotonic() - batch_start, 2),
            )

            if on_progress:
                on_progress(completed, total)

            # Brief pause between batches to stay under the free-tier quota
            # (100 embed_content requests per minute = ~0.6s between requests)
            # Skip after the last batch
            if batch_num < n_batches:
                time.sleep(0.7)

        logger.info(
            "Batch embedding complete: %d vectors generated for %d chunks",
            len(all_vectors),
            total,
        )

        return all_vectors


def _batched(items: list, size: int) -> Iterator[list]:
    """Yield successive sublists of length `size`."""
    for i in range(0, len(items), size):
        yield items[i : i + size]
