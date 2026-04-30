"""Vertex AI service abstractions."""

from __future__ import annotations

import logging

logger = logging.getLogger("app.services.vertex_ai_service")

EMBEDDING_FALLBACK_LOCATIONS = ("us-central1",)


def _init_vertex_ai(vertexai: object, *, project_id: str, location: str) -> None:
    """Initialize Vertex AI with a validated regional location.

    The ``google-cloud-aiplatform`` SDK rejects ``"global"`` during region
    validation.  Instead of relying on the ``api_endpoint`` workaround (which
    contaminates the SDK-level global config and breaks subsequent regional
    calls), we map ``"global"`` to ``"us-central1"`` — the broadest-coverage
    region for Gemini models.

    Additionally, any previously set ``api_endpoint`` is explicitly cleared
    to prevent stale values from rerouting requests.
    """
    # Clear any previously set global api_endpoint to prevent contamination
    # from prior init() calls.  The SDK does NOT reset this value even when
    # api_endpoint=None is passed to init().
    try:
        from google.cloud import aiplatform
        aiplatform.initializer.global_config._api_endpoint = None
    except Exception:  # noqa: BLE001
        pass

    resolved_location = location
    if location.lower() == "global":
        resolved_location = "us-central1"

    vertexai.init(project=project_id, location=resolved_location)


def _is_model_not_found_error(exc: Exception) -> bool:
    """Check if the exception indicates the model is not available in the region."""
    error_text = str(exc).lower()
    return "not found" in error_text or "404" in error_text


class VertexAIEmbeddingService:
    """Facade for Vertex AI embedding calls."""

    def __init__(
        self,
        project_id: str,
        location: str,
        model_name: str,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self._effective_location: str | None = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings with Vertex AI.

        If the configured location does not support the embedding model,
        automatically retries with fallback locations (e.g. us-central1).
        """
        try:
            import vertexai
            from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
        except ImportError as exc:
            raise RuntimeError("google-cloud-aiplatform is required for Vertex AI embeddings.") from exc

        inputs = [TextEmbeddingInput(text=text, task_type="RETRIEVAL_DOCUMENT") for text in texts]

        # If a previous call already discovered a working fallback location, use it directly.
        if self._effective_location and self._effective_location != self.location:
            return self._call_embedding(vertexai, TextEmbeddingModel, inputs, self._effective_location)

        # Try the configured location first.
        try:
            result = self._call_embedding(vertexai, TextEmbeddingModel, inputs, self.location)
            self._effective_location = self.location
            return result
        except Exception as primary_exc:  # noqa: BLE001
            if not _is_model_not_found_error(primary_exc):
                raise

            logger.warning(
                "embedding_model_not_found_in_primary_location",
                extra={
                    "model_name": self.model_name,
                    "primary_location": self.location,
                    "error": str(primary_exc),
                },
            )

        # Try fallback locations.
        for fallback_location in EMBEDDING_FALLBACK_LOCATIONS:
            if fallback_location == self.location:
                continue
            try:
                result = self._call_embedding(vertexai, TextEmbeddingModel, inputs, fallback_location)
                logger.info(
                    "embedding_fallback_location_succeeded",
                    extra={
                        "model_name": self.model_name,
                        "fallback_location": fallback_location,
                    },
                )
                self._effective_location = fallback_location
                return result
            except Exception:  # noqa: BLE001
                logger.warning(
                    "embedding_fallback_location_failed",
                    extra={
                        "model_name": self.model_name,
                        "fallback_location": fallback_location,
                    },
                )

        raise RuntimeError(
            f"Embedding model '{self.model_name}' is not available in '{self.location}' "
            f"or any fallback locations {EMBEDDING_FALLBACK_LOCATIONS}."
        )

    def _call_embedding(
        self, vertexai: object, model_class: type, inputs: list, location: str
    ) -> list[list[float]]:
        """Execute the embedding call against a specific location."""
        _init_vertex_ai(vertexai, project_id=self.project_id, location=location)
        model = model_class.from_pretrained(self.model_name)
        outputs = model.get_embeddings(inputs)
        return [list(output.values) for output in outputs]


class VertexAIGenerationService:
    """Facade for Gemini text generation calls."""

    def __init__(self, project_id: str, location: str, model_name: str) -> None:
        self.project_id = project_id
        self.location = location
        self.model_name = model_name

    def generate_text(self, prompt: str) -> str:
        """Generate text with Gemini."""
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
        except ImportError as exc:
            raise RuntimeError("google-cloud-aiplatform is required for Gemini generation.") from exc

        _init_vertex_ai(vertexai, project_id=self.project_id, location=self.location)
        model = GenerativeModel(self.model_name)
        response = model.generate_content(prompt)
        return str(response.text).strip()
