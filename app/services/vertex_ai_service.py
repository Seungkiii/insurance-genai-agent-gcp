"""Vertex AI service abstractions."""

from __future__ import annotations


def _init_vertex_ai(vertexai: object, *, project_id: str, location: str) -> None:
    """Initialize Vertex AI, using the documented global endpoint behavior when needed."""
    init_kwargs = {"project": project_id, "location": location}
    if location.lower() == "global":
        init_kwargs["api_endpoint"] = "aiplatform.googleapis.com"
    vertexai.init(**init_kwargs)


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

        _init_vertex_ai(vertexai, project_id=self.project_id, location=self.location)
        model = TextEmbeddingModel.from_pretrained(self.model_name)
        inputs = [TextEmbeddingInput(text=text, task_type="RETRIEVAL_DOCUMENT") for text in texts]
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
