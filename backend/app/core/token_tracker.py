"""
Token usage tracker for Gemini API calls.

Wraps the google-genai client to capture token usage metadata from every
generate_content call and log it as structured data.

Usage:
    from app.core.token_tracker import track_usage

    response = client.models.generate_content(...)
    track_usage(response, operation="investigation", model="gemini-2.5-flash")
"""

from app.core.logging import get_logger

logger = get_logger(__name__)


def track_usage(response, *, operation: str, model: str) -> None:
    """
    Extract and log token usage from a Gemini GenerateContentResponse.

    Args:
        response: The GenerateContentResponse object from the Gemini SDK.
        operation: A label for what this call is for (e.g. "investigation", "chat").
        model: The model name used.
    """
    try:
        meta = response.usage_metadata
        if meta is None:
            return

        prompt_tokens = getattr(meta, "prompt_token_count", None)
        output_tokens = getattr(meta, "candidates_token_count", None)
        total_tokens = getattr(meta, "total_token_count", None)

        logger.info(
            "Token usage: operation=%s model=%s prompt=%s output=%s total=%s",
            operation,
            model,
            prompt_tokens,
            output_tokens,
            total_tokens,
        )
    except Exception as exc:
        # Never let tracking failure affect the main request
        logger.debug("Token tracking failed: %s", exc)
