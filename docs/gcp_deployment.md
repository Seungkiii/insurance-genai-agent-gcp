# GCP Cloud Run 배포 가이드

## 개요

이 프로젝트는 `FastAPI` 애플리케이션을 컨테이너로 패키징한 뒤 `GCP Cloud Run`에 배포할 수 있도록 구성되어 있습니다. 포트폴리오용 MVP이기 때문에 구조는 단순하게 유지하되, 실제 운영 환경으로 확장할 수 있는 방향을 함께 고려했습니다.

기본 전제는 다음과 같습니다.

- 애플리케이션은 stateless container로 동작
- MVP 테스트용 synthetic sample 데이터는 이미지에 포함 가능
- 민감한 설정값은 저장소가 아니라 외부에서 주입
- Cloud Run의 scale-to-zero 특성을 적극 활용

## 배포 관련 파일

주요 파일:

- `Dockerfile`
- `.dockerignore`
- `infra/deploy-cloud-run.yml`

## 권장 GCP 서비스 구성

- `Cloud Run`: 컨테이너 실행
- `Artifact Registry`: 컨테이너 이미지 저장
- `Secret Manager`: 환경변수 및 민감 정보 주입
- `Vertex AI`: 향후 generation / embedding 연동
- `Firestore`: 세션, 피드백, 설계 이력 저장 확장 포인트
- `Cloud Storage`: 약관 문서 저장 및 업로드 확장 포인트

## Container Build

현재 `Dockerfile`은 다음 기준으로 작성되어 있습니다.

- `python:3.11-slim` 사용
- `requirements.txt` 기반 의존성 설치
- `app`, `data`, `docs`, `README.md`만 이미지에 복사
- `PORT=8080` 기준으로 `uvicorn` 실행

로컬 build 예시:

```bash
docker build -t insurance-genai-agent-api:local .
```

로컬 실행 예시:

```bash
docker run --rm -p 8080:8080 insurance-genai-agent-api:local
```

## GitHub Actions 배포 흐름

배포 workflow 템플릿은 아래 파일에 있습니다.

- `infra/deploy-cloud-run.yml`

흐름은 다음과 같습니다.

1. repository checkout
2. `Workload Identity Federation`으로 Google Cloud 인증
3. `Artifact Registry`용 Docker 인증 설정
4. Docker image build
5. image push
6. `gcloud run deploy` 실행

GitHub repository secrets 예시:

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`

주의:

- 현재 파일은 배포 템플릿입니다
- 실제 GitHub Actions로 자동 실행하려면 `.github/workflows/` 아래로 옮기거나 복사해야 합니다

## 환경변수 전략

Cloud Run 배포에서는 `.env` 파일 사용을 권장하지 않습니다.

권장 방식:

- 민감한 값은 `Secret Manager`에 저장
- Cloud Run runtime service account에 필요한 secret만 접근 권한 부여
- 배포 시 `--update-secrets`로 주입
- 민감하지 않은 기본값만 일반 환경변수로 관리

왜 `Secret Manager`를 권장하는가:

- Git history에 비밀값이 남지 않음
- secret rotation이 쉬움
- IAM 기반 접근 제어 가능
- 감사 추적이 가능함
- `dev / staging / prod` 분리가 쉬움

## 권장 환경변수 목록

실제 프로젝트 ID나 실제 secret 값은 저장소에 넣지 말고, 아래와 같은 이름만 기준으로 관리하는 것을 권장합니다.

### Core App

- `ENVIRONMENT`
- `PORT`
- `APP_NAME`
- `APP_VERSION`

### Vertex AI

- `VERTEX_AI_PROJECT_ID`
- `VERTEX_AI_LOCATION`
- `VERTEX_AI_MODEL_NAME`
- `VERTEX_AI_EMBEDDING_MODEL_NAME`

### Firestore

- `FIRESTORE_PROJECT_ID`
- `FIRESTORE_DATABASE`
- `FIRESTORE_COLLECTION_SESSIONS`
- `FIRESTORE_COLLECTION_FEEDBACK`

### Cloud Storage

- `GCS_PROJECT_ID`
- `GCS_BUCKET_NAME`
- `GCS_POLICY_PREFIX`
- `GCS_SAMPLE_DATA_PREFIX`

### 선택 운영 옵션

- `LOG_LEVEL`
- `ENABLE_MCP_SERVER`
- `DEFAULT_POLICY_PATH`
- `DEFAULT_HISTORY_PATH`

## Secret Manager 사용 예시

예시 명령:

```bash
gcloud run deploy insurance-genai-agent-api \
  --image=YOUR_IMAGE_URI \
  --region=YOUR_REGION \
  --min-instances=0 \
  --max-instances=2 \
  --update-secrets=VERTEX_AI_PROJECT_ID=vertex-ai-project-id:latest,GCS_BUCKET_NAME=gcs-bucket-name:latest
```

이 방식은 실제 secret 값을 workflow YAML이나 저장소에 남기지 않는다는 점에서 안전합니다.

## 비용 절감을 위한 Cloud Run 설정

MVP 기준 권장 설정:

- `min-instances=0`
- `max-instances=1` 또는 `2`
- `cpu=1`
- `memory=512Mi`
- `concurrency=10`

비용 절감 관점에서의 의미:

- idle 상태에서는 scale-to-zero로 비용 최소화
- 과도한 병렬 확장 방지
- 메모리 과할당 방지
- PoC 단계에서 항상 켜져 있는 instance 비용 방지

## 배포 시 참고 사항

- Vertex AI, Firestore, Cloud Storage를 아직 연결하지 않았다면 관련 환경변수는 placeholder 상태로 두거나 비워둘 수 있습니다
- synthetic sample만 사용하는 공개 데모라면 `--allow-unauthenticated`도 선택 가능하지만, 운영 환경에 가까워질수록 인증 적용을 권장합니다
- 실제 운영 전환 시에는 최소 권한 원칙에 맞는 service account 설계가 필요합니다

## 향후 개선 방향

- `infra/deploy-cloud-run.yml`를 `.github/workflows/`로 이동
- `staging` / `production` 분리 배포
- Cloud Run service account IAM 예시 추가
- 배포 후 health-check smoke test 추가
- rollback 절차 문서화
