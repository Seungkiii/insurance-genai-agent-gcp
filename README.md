# insurance-genai-agent-gcp

GCP 기반 보험 가입설계 자동화 GenAI Agent PoC를 위한 FastAPI 백엔드 스캐폴딩 프로젝트입니다.

## 개요
- 목적: 보험설계사(FC) 업무 지원형 GenAI Agent PoC 구조 검증
- 범위: RAG, Agent Workflow, MCP Tool Server, GCP 서비스 레이어 분리
- 데이터: 모든 샘플은 synthetic/dummy 데이터만 사용

## 빠른 시작
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API
- `GET /api/v1/health`
- `POST /api/v1/chat`
- `POST /api/v1/documents/upload`
- `POST /api/v1/documents/index`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/feedback`
- `GET /api/v1/admin/failed-questions`
- `GET /api/v1/admin/statistics`

## 보안/데이터 원칙
- 실제 보험사명, 실제 RFP, 실제 고객정보, 내부 API 정보 미포함
- 모든 문서/데이터는 포트폴리오용 샘플
