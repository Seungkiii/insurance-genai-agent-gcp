# Insurance RAG Pipeline

이 프로젝트의 RAG는 특정 상품 하나에 맞춘 튜닝이 아니라, 보험상품 문서의 공통 구조를 활용하는 범용 검색 파이프라인을 목표로 합니다.

## 핵심 원칙

- 특정 상품명, 특정 보험금명, 특정 PDF 파일명, 특정 페이지 번호에 대한 하드코딩을 두지 않습니다.
- `product_type`, `document_type`, `normalized_section` metadata를 인덱싱 단계에서 생성합니다.
- 질문 intent를 `search_profile`로 분류하고, profile별 query expansion과 section boost를 적용합니다.
- cosine similarity만 사용하지 않고 hybrid retrieval score를 사용합니다.
- confidence score는 검색 점수뿐 아니라 intent-section 정합성과 citation 품질을 반영합니다.

## 인덱싱 단계

1. PDF 업로드
2. PDF 파싱
3. 문서 수준 metadata 생성
   - `product_type`
   - `document_type`
4. 섹션 수준 metadata 생성
   - 원문 `section`
   - 정규화된 `normalized_section`
5. chunk 생성
6. chunk embedding 생성
7. GCS에 `chunks.jsonl`, `embeddings.jsonl` 저장

## 검색 단계

1. 질문을 `search_profile`로 분류
2. profile에 맞는 expansion terms를 붙여 `expanded_query` 생성
3. expanded query embedding 생성
4. candidate chunk에 대해:
   - embedding score 계산
   - section boost
   - document type boost
   - product type boost
   - exact keyword boost
   - negative section penalty
5. hybrid score 기준 정렬
6. 문서/섹션 다양성을 유지하며 최종 citation 선택

## 확장성

현재 구조는 GCS JSONL 기반이지만, metadata와 search profile이 분리되어 있어 Vertex AI Vector Search나 별도 vector DB로 확장하기 쉽습니다.
