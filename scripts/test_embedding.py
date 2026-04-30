"""Quick diagnostic script to test embedding model availability across regions."""
import sys

PROJECT_ID = "insurance-aiagent-project"
MODEL_NAME = "text-multilingual-embedding-002"
LOCATIONS = ["asia-northeast3", "us-central1", "asia-northeast1", "global"]

try:
    import vertexai
    from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
except ImportError:
    print("ERROR: google-cloud-aiplatform is not installed")
    sys.exit(1)

print(f"Project: {PROJECT_ID}")
print(f"Model: {MODEL_NAME}")
print(f"Testing locations: {LOCATIONS}")
print("-" * 60)

for location in LOCATIONS:
    try:
        init_kwargs = {"project": PROJECT_ID, "location": location}
        if location.lower() == "global":
            init_kwargs["api_endpoint"] = "aiplatform.googleapis.com"
        vertexai.init(**init_kwargs)
        model = TextEmbeddingModel.from_pretrained(MODEL_NAME)
        inputs = [TextEmbeddingInput(text="보험 테스트", task_type="RETRIEVAL_DOCUMENT")]
        outputs = model.get_embeddings(inputs)
        dim = len(outputs[0].values)
        print(f"  ✅ {location}: SUCCESS (dim={dim})")
    except Exception as exc:
        print(f"  ❌ {location}: FAILED - {exc}")

print("-" * 60)
print("Done.")
