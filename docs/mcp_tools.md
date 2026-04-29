# MCP-Compatible Tools

## 개요

현재 Tool Server는 실제 MCP SDK 자체를 직접 사용하지는 않지만, MCP로 전환하기 쉬운 인터페이스를 유지하도록 설계되어 있습니다. 핵심은 tool 실행 계약을 표준화하고, business logic을 transport/runtime과 분리하는 것입니다.

## 공통 계약

모든 tool은 `BaseTool`을 상속하고 아래 메타데이터를 가집니다.

- `name`
- `description`
- `input_schema`
- `output_schema`
- `run(payload)`

`run()`은 내부 `execute()`를 호출하고, 항상 `ToolResult` 표준 포맷으로 감싼 결과를 반환합니다.

### ToolResult 포맷

- `tool_name`
- `status`
- `input`
- `output`
- `latency_ms`
- `error`
- `trace_summary`

이 포맷 덕분에 Agent는 tool마다 다른 성공/실패 포맷을 해석하지 않고 동일한 방식으로 로그와 fallback을 처리할 수 있습니다.

## Tool별 역할

### `policy_search_tool`

- 질문을 `search_profile`로 분류합니다.
- `expanded_query`를 생성합니다.
- `product_type`, `document_type`, `normalized_section` metadata를 가진 hybrid retriever를 호출합니다.
- output에는 `chunks`, `citations`, `search_profile`, `product_type`, `document_type`, `normalized_section`, `confidence_signal`, `fallback_required`가 포함됩니다.

### `product_recommend_tool`

- 내부적으로 `policy_search_tool`을 호출합니다.
- 검색된 근거를 기반으로 상품군별 요약 구조를 만듭니다.
- 임의 가입금액, 확정 추천, 심사 결과를 생성하지 않습니다.
- output에는 `recommended_design`, `evidence_summary`, `citations`, `caution_notes`가 포함됩니다.

### `design_condition_tool`

- Firestore에서 `session_id` 기준 `current_design`을 조회합니다.
- `add_coverages`, `remove_coverages`, `keep_coverages`를 반영합니다.
- `previous_design`과 `updated_design`을 함께 반환합니다.
- Firestore 저장 실패 시에도 예외를 그대로 퍼뜨리지 않고 `ToolResult.status=error`로 반환할 수 있게 설계되어 있습니다.

## 실제 MCP SDK 전환 포인트

현재 구조는 다음 이유로 MCP SDK 전환이 쉽습니다.

1. tool 메타데이터와 실행 함수가 이미 분리되어 있습니다.
2. input/output schema가 명시적으로 존재합니다.
3. 결과 포맷이 `ToolResult`로 표준화되어 있습니다.
4. business logic은 `execute()` 내부에 있어 런타임만 교체하면 됩니다.

전환 순서는 보통 다음과 같습니다.

1. `MCPToolServer` registry를 실제 MCP SDK server registration으로 교체
2. 각 tool의 `name`, `description`, `input_schema`, `output_schema`를 SDK tool declaration에 매핑
3. `run()` 또는 `execute()`를 SDK handler로 연결
4. transport를 stdio, websocket, hosted runtime 중 원하는 방식으로 선택

즉 현재 구조는 “보험상품 문서 RAG + 추천 + 설계변경” 비즈니스 로직을 그대로 유지한 채 MCP runtime만 바꾸는 방향을 전제로 하고 있습니다.
