# Evaluation Plan

## 목적

평가는 특정 PDF 하나를 맞추는 것이 아니라, 보험상품군 전반에서 intent별 검색 품질을 검증하는 데 목적이 있습니다.

## 평가 데이터셋

`data/evaluation/insurance_rag_eval_questions.json`에는 다음 상품군의 질문 세트가 포함됩니다.

- 연금보험
- 종신보험
- 암보험
- 건강보험
- 상해보험
- 치아보험

각 항목은 다음 필드를 가집니다.

- `question`
- `expected_profile`
- `expected_product_type`
- `expected_positive_sections`
- `expected_negative_sections`
- `required_keywords`

## 자동 테스트 범위

- product type 분류
- document type 분류
- normalized section 분류
- search profile 분류
- query expansion
- hybrid retrieval scoring
- confidence score

모든 테스트는 synthetic text와 synthetic chunk metadata로 검증 가능하도록 작성합니다. 실제 PDF 내용이나 특정 페이지 번호에 의존하지 않습니다.

## Confidence Score 원칙

confidence는 검색 점수만으로 계산하지 않습니다.

- retrieval 점수
- positive section 일치도
- preferred document type 포함 여부
- negative section 비율
- citation 다양성
- fallback 여부
- generator의 근거 부족 신호

예를 들어 `coverage_summary` 질문인데 `premium`, `refund`, `fee` chunk가 대부분이면 confidence를 낮춥니다.

## 향후 확장

현재 평가는 JSONL + GCS 기반 retrieval에 맞춰져 있지만, 같은 metadata와 profile 구조를 유지하면 Vertex AI Vector Search 기반으로도 확장 가능합니다.
