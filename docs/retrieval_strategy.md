# Retrieval Strategy

## 목표

여러 보험상품군에서도 안정적으로 동작하는 retrieval 구조를 유지하는 것입니다. 이 전략은 특정 상품이 아니라 보험상품 문서의 공통 구조를 중심으로 설계되었습니다.

## Metadata 축

- `product_type`
  - annuity
  - whole_life
  - cancer
  - health
  - accident
  - dental
  - simplified
  - custom_coverage
  - unknown
- `document_type`
  - product_summary
  - business_method
  - policy_terms
  - unknown
- `normalized_section`
  - product_overview
  - eligibility
  - coverage
  - exclusions
  - annuity_payment
  - death_benefit
  - cancer_benefit
  - health_benefit
  - accident_benefit
  - dental_benefit
  - premium
  - refund
  - fee
  - claim
  - rider
  - miscellaneous

## Intent 기반 Search Profile

질문은 `coverage_summary`, `pension_payment`, `premium_cost`, `surrender_refund`, `claim_document` 같은 profile로 분류됩니다.

각 profile은 다음을 정의합니다.

- expansion terms
- positive sections
- negative sections
- preferred document types
- product type hints

예를 들어 `coverage_summary`는 `coverage`, `product_overview`, `rider`, `exclusions`를 우선하고 `premium`, `refund`, `fee`는 감점합니다.

## Hybrid Retrieval Score

최종 정렬은 cosine similarity만으로 하지 않고 아래 요소를 합산합니다.

- embedding score
- section boost
- document type boost
- product type boost
- exact keyword boost
- negative section penalty

또한 한 문서의 같은 페이지나 같은 섹션이 과도하게 반복되지 않도록 diversity selection을 적용합니다.

## Multi-document Retrieval

- `document_ids`가 있으면 해당 문서 안에서만 검색합니다.
- `document_ids`가 없으면 indexed 문서 전체를 후보로 사용합니다.
- `top_k_per_document`를 통해 한 문서가 결과를 독점하지 않도록 제어합니다.
- `product_comparison` 같은 profile은 여러 문서에서 균형 있게 citation을 가져올 수 있도록 설계되어 있습니다.
