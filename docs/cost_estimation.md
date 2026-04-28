# 비용 추정 및 절감 전략

## 개요

이 문서는 synthetic sample 기반 Insurance GenAI Agent MVP를 `GCP`에서 운영할 때의 비용 전략을 설명하기 위한 포트폴리오용 문서입니다. 실제 청구 금액을 보장하는 문서는 아니며, 실제 비용은 region, 요청량, 모델 사용량, 저장 용량, 네트워크 사용량에 따라 달라집니다.

이 MVP의 목적은 아래 항목을 **낮은 비용으로 검증**하는 것입니다.

- `Cloud Run` 기반 API 배포
- 약관 검색 흐름
- 가입설계 추천 흐름
- MCP-compatible tool orchestration

## 비용 통제 원칙

- `Cloud Run`의 scale-to-zero 적극 활용
- instance 수를 낮게 제한
- 항상 켜져 있는 인프라 최소화
- 기능 검증 전에는 live LLM / embedding 호출 지연
- 대용량 실제 데이터 대신 synthetic sample 데이터 사용

## 권장 MVP 기본 설정

Cloud Run 기준 권장값:

- `min-instances=0`
- `max-instances=1` 또는 `2`
- `cpu=1`
- `memory=512Mi`
- `concurrency=10`

기대 효과:

- 트래픽이 없을 때 idle compute 비용 최소화
- 데모 상황에서의 burst 비용 제한
- 예기치 않은 자동 확장 억제

## 서비스별 비용 관점

### Cloud Run

주요 비용 요인:

- request 수
- instance 실행 시간
- CPU / memory 할당량

절감 팁:

- `min-instances=0` 유지
- `max-instances`를 낮게 유지
- memory를 과하게 주지 않기
- container startup 시 무거운 작업 피하기

### Artifact Registry

주요 비용 요인:

- 저장된 image 크기
- 보관 중인 image revision 수

절감 팁:

- image를 가볍게 유지
- 불필요한 tag 정리
- 로컬 테스트 파일이 image에 들어가지 않도록 `.dockerignore` 관리

### Secret Manager

주요 비용 요인:

- secret 수
- secret access 횟수

절감 팁:

- 정말 필요한 runtime 민감 정보만 저장
- 관련 설정은 적절히 묶되 과도하게 합치지는 않기

### Firestore

주요 비용 요인:

- document read
- write
- 저장 용량

절감 팁:

- 세션과 피드백 등 꼭 필요한 데이터만 저장
- MVP성 임시 데이터에는 TTL 또는 정리 정책 고려
- 전체 대화 로그를 무조건 장기 보관하지 않기

### Cloud Storage

주요 비용 요인:

- 저장 용량
- operation 수
- egress

절감 팁:

- MVP 단계에서는 synthetic sample 약관 문서만 유지
- version 보관은 꼭 필요할 때만 사용
- 큰 binary 테스트 파일 업로드 최소화

### Vertex AI

주요 비용 요인:

- embedding 호출 수
- text generation 호출 수
- 선택한 model 종류

절감 팁:

- 초기에는 현재 keyword retriever 유지
- retrieval UX가 검증된 뒤 embedding 활성화
- 대량 batch indexing보다 작은 테스트 세트부터 시작
- retrieval 평가와 generation 평가를 분리

## 왜 `min-instances=0`가 중요한가

포트폴리오용 MVP는 일반적으로 트래픽이 간헐적입니다. `min-instances=0`이면:

- idle 시 자동으로 scale-to-zero
- 항상 켜진 instance 비용을 줄일 수 있음
- 데모 사이 시간대의 불필요한 비용을 아낄 수 있음

tradeoff:

- cold start가 발생할 수 있음

하지만 이 프로젝트에서는 그 tradeoff가 충분히 수용 가능합니다.

## 왜 `max-instances=1~2`가 중요한가

이 프로젝트는 synthetic sample 기반 MVP이기 때문에:

- 처리량 요구가 낮고
- 실제 production 수준 트래픽이 아니며
- 과도한 자동 확장보다 비용 예측 가능성이 더 중요합니다

낮은 상한은 다음 장점이 있습니다.

- 비용 예측이 쉬움
- 디버깅이 단순해짐
- 새로운 모델 연동 시 예기치 않은 비용 폭증 방지

## 단계별 운영 시나리오

### Stage 1: Retrieval-only MVP

사용:

- Cloud Run
- Artifact Registry
- Secret Manager

보류:

- Vertex AI generation
- Firestore persistence
- 대규모 Cloud Storage ingestion

가장 저렴한 초기 검증 단계입니다.

### Stage 2: Retrieval + Recommendation

사용:

- Cloud Run
- Artifact Registry
- Secret Manager
- 필요 시 Firestore

추천 기능이 추가되더라도 비교적 가벼운 단계입니다.

### Stage 3: Retrieval + Recommendation + Vertex AI

사용:

- Cloud Run
- Artifact Registry
- Secret Manager
- Firestore
- Cloud Storage
- Vertex AI

이 단계부터는 model 호출량이 주요 변수 비용이 됩니다.

## 운영 가드레일

- 배포 환경에서는 `.env` 대신 `Secret Manager` 사용
- Cloud Run revision 설정 변경 전 CPU / memory / max instance 확인
- API 트래픽과 model 사용량을 별도로 모니터링
- 사용하지 않는 image revision과 테스트 리소스 정리

## 포트폴리오 관점에서의 메시지

이 문서에서 중요한 것은 “정확히 월 얼마가 든다”가 아니라, 처음부터 아키텍처가 아래 원칙을 따르도록 설계되었다는 점입니다.

- scale-to-zero 중심 설계
- 초기에는 관리형 서비스 사용 범위 최소화
- retrieval / recommendation / generation 비용 분리
- 필요성이 확인된 뒤 Vertex AI를 점진적으로 활성화
