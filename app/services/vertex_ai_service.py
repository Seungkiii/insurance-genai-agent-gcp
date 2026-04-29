"""Vertex AI service abstractions."""

from __future__ import annotations


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

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings with Vertex AI."""
        try:
            import vertexai
            from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
        except ImportError as exc:
            raise RuntimeError("google-cloud-aiplatform is required for Vertex AI embeddings.") from exc

        vertexai.init(project=self.project_id, location=self.location)
        model = TextEmbeddingModel.from_pretrained(self.model_name)
        inputs = [TextEmbeddingInput(text=text, task_type="RETRIEVAL_DOCUMENT") for text in texts]
        outputs = model.get_embeddings(inputs)
        return [list(output.values) for output in outputs]
