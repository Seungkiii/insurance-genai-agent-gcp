"""Final E2E test: Generation (global→us-central1) → Embedding (asia-northeast3) cycle."""
import sys
sys.path.insert(0, ".")

PROJECT_ID = "insurance-aiagent-project"

try:
    import vertexai
    from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
    from vertexai.generative_models import GenerativeModel
    from google.cloud import aiplatform
    from app.services.vertex_ai_service import _init_vertex_ai
except ImportError as exc:
    print(f"ERROR: {exc}")
    sys.exit(1)

print("=== Final E2E: Generation (global) → Embedding (asia-northeast3) ===")

# Question 1: generation call (simulating response_node with non-general intent)
print("\n1. Generation with location='global' (mapped to us-central1)...")
_init_vertex_ai(vertexai, project_id=PROJECT_ID, location="global")
ep = getattr(aiplatform.initializer.global_config, 'api_endpoint', 'NOT SET')
loc = getattr(aiplatform.initializer.global_config, 'location', 'NOT SET')
print(f"   api_endpoint={ep}, location={loc}")
try:
    model = GenerativeModel("gemini-2.5-flash-lite")
    response = model.generate_content("'안녕하세요' 한마디만")
    print(f"   ✅ Generation OK: {response.text.strip()[:50]}")
except Exception as exc:
    print(f"   ❌ Generation FAILED: {exc}")

# Question 2: embedding call (simulating policy_search_tool)
print("\n2. Embedding with location='asia-northeast3'...")
_init_vertex_ai(vertexai, project_id=PROJECT_ID, location="asia-northeast3")
ep = getattr(aiplatform.initializer.global_config, 'api_endpoint', 'NOT SET')
loc = getattr(aiplatform.initializer.global_config, 'location', 'NOT SET')
print(f"   api_endpoint={ep}, location={loc}")
try:
    model = TextEmbeddingModel.from_pretrained("text-multilingual-embedding-002")
    inputs = [TextEmbeddingInput(text="보험 주요 보장 내용", task_type="RETRIEVAL_DOCUMENT")]
    outputs = model.get_embeddings(inputs)
    print(f"   ✅ Embedding OK (dim={len(outputs[0].values)})")
except Exception as exc:
    print(f"   ❌ Embedding FAILED: {exc}")

# Question 2 continued: generation call
print("\n3. Generation with location='global' again (after embedding)...")
_init_vertex_ai(vertexai, project_id=PROJECT_ID, location="global")
try:
    model = GenerativeModel("gemini-2.5-flash-lite")
    response = model.generate_content("'감사합니다' 한마디만")
    print(f"   ✅ Generation OK: {response.text.strip()[:50]}")
except Exception as exc:
    print(f"   ❌ Generation FAILED: {exc}")

# Question 3: embedding again
print("\n4. Embedding with location='asia-northeast3' again...")
_init_vertex_ai(vertexai, project_id=PROJECT_ID, location="asia-northeast3")
try:
    model = TextEmbeddingModel.from_pretrained("text-multilingual-embedding-002")
    inputs = [TextEmbeddingInput(text="해약환급금 조건", task_type="RETRIEVAL_DOCUMENT")]
    outputs = model.get_embeddings(inputs)
    print(f"   ✅ Embedding OK (dim={len(outputs[0].values)})")
except Exception as exc:
    print(f"   ❌ Embedding FAILED: {exc}")

print("\n=== ALL DONE ===")
