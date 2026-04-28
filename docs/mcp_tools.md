# MCP Tool Server MVP

## 개요

이 프로젝트에는 포트폴리오 설명과 로컬 workflow 연동을 위한 `MCP-compatible Tool Server MVP`가 포함되어 있습니다. 현재 구현은 실제 MCP SDK를 바로 붙인 형태는 아니고, MCP의 핵심 개념을 설명할 수 있는 가벼운 registry 패턴으로 구성되어 있습니다.

이 구조로 보여주고 싶은 포인트는 다음과 같습니다.

- tool 단위 책임 분리
- 검색 가능한 tool metadata 제공
- 구조화된 input / output schema 정의
- 명시적인 `run` 실행 계약
- 이후 실제 MCP SDK로의 전환 가능성

구현 진입점:

- `app/mcp_server/server.py`

tool 파일:

- `app/mcp_server/tools/policy_search_tool.py`
- `app/mcp_server/tools/product_recommend_tool.py`
- `app/mcp_server/tools/design_condition_tool.py`

## MCP-Compatible Interface

각 tool은 아래 공통 필드와 메서드를 가집니다.

- `name`
- `description`
- `input_schema`
- `output_schema`
- `run(payload)`

이 형태는 실제 MCP tool 선언 방식과 최대한 유사하게 맞추면서도, 포트폴리오 MVP 수준에서는 복잡도를 낮추기 위한 선택입니다.

## Tool Registry

`MCPToolServer`는 로컬 registry이자 실행 레이어 역할을 합니다.

지원 메서드:

- `list_tools()`: tool metadata 목록 반환
- `call_tool(name, payload)`: 이름으로 tool 실행

이 구조 덕분에 아래 경계를 설명하기 쉬워집니다.

- Agent orchestration
- business / domain tools
- transport / runtime layer

## Tool 구성

### 1. `policy_search_tool`

역할:

- synthetic sample 약관 검색
- 관련 조항과 citation metadata 반환

구현 방식:

- 기존 keyword 기반 RAG retriever 호출
- `sample_policy.md` 문서 파이프라인 재사용

입력 예시:

```json
{
  "query": "입원일당 청구 서류는 무엇인가요?",
  "top_k": 3
}
```

### 2. `product_recommend_tool`

역할:

- synthetic 가입설계 이력 기반 추천 수행

구현 방식:

- `recommendation_service` 호출
- `age_group`, `gender`, `product_name` 기준 필터링
- rider 추천, payment 설정, coverage amount, `confidence_score`, `basis_count` 반환

입력 예시:

```json
{
  "age_group": "30s",
  "gender": "F",
  "product_name": "Sample Care Plan"
}
```

### 3. `design_condition_tool`

역할:

- 현재 synthetic 설계 상태에 rider add / remove 적용

구현 방식:

- `current_design` object 입력
- `add_riders`, `remove_riders` 반영
- 수정된 설계와 적용 결과 반환

입력 예시:

```json
{
  "current_design": {
    "product_name": "Sample Care Plan",
    "payment_period": "20 years",
    "insurance_period": "80 years",
    "payment_cycle": "monthly",
    "coverage_amount": 50000000,
    "riders": ["Standard Hospital Rider"]
  },
  "add_riders": ["Critical Diagnosis Rider"],
  "remove_riders": ["Standard Hospital Rider"]
}
```

## 왜 이 구조가 포트폴리오에 좋은가

이 구조의 장점은 policy retrieval, recommendation, design modification을 Agent 내부 한 함수에 숨기지 않고, 각각을 명확한 tool로 분리했다는 점입니다.

즉 각 기능은 다음 특징을 가집니다.

- 도메인 목적이 분명함
- interface contract가 명확함
- 재사용 가능함
- 이후 다른 구현으로 교체하기 쉬움

그래서 “GenAI 시스템이 monolithic prompt logic에서 modular tool orchestration으로 어떻게 진화하는가”를 설명하기에 적합합니다.

## 향후 MCP SDK 전환 계획

현재 버전은 의도적으로 SDK 의존성을 최소화했습니다. 이후 실제 MCP SDK로 전환할 때는 아래 순서로 진행할 수 있습니다.

1. 로컬 `MCPToolServer` registry를 MCP SDK server runtime으로 교체
2. 각 tool을 SDK 방식으로 등록
3. `input_schema`, `output_schema`를 SDK native schema로 매핑
4. 기존 `run` 로직은 그대로 실행 본문으로 재사용
5. 원하는 MCP transport layer로 노출

핵심은 현재도 비즈니스 로직이 이미 tool 단위로 분리되어 있기 때문에, 전환 작업이 로직 재작성보다는 runtime/registration 레벨에 집중된다는 점입니다.

## 데이터 안전성

현재 모든 tool은 synthetic sample 데이터만 사용합니다. 실제 보험사 데이터, 실제 고객정보, 실제 운영 API 계약은 포함하지 않습니다.
