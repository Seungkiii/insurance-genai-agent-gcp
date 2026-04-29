"""API health and readiness tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health_endpoints_return_process_status(monkeypatch) -> None:
    """Both health endpoints should return basic process metadata."""
    monkeypatch.setenv("APP_NAME", "Insurance GenAI Agent API")
    monkeypatch.setenv("APP_VERSION", "0.1.0-test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    client = TestClient(create_app())

    for path in ("/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "service": "Insurance GenAI Agent API",
            "environment": "test",
            "version": "0.1.0-test",
        }


def test_ready_endpoints_return_missing_settings_when_not_configured(monkeypatch) -> None:
    """Both ready endpoints should show missing required settings when unset."""
    monkeypatch.setenv("APP_NAME", "Insurance GenAI Agent API")
    monkeypatch.setenv("APP_VERSION", "0.1.0-test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    for key in (
        "VERTEX_AI_PROJECT_ID",
        "VERTEX_AI_LOCATION",
        "VERTEX_AI_EMBEDDING_LOCATION",
        "VERTEX_AI_GENERATION_LOCATION",
        "FIRESTORE_DATABASE",
        "GCS_BUCKET_NAME",
        "GEMINI_MODEL_NAME",
        "EMBEDDING_MODEL_NAME",
    ):
        monkeypatch.delenv(key, raising=False)

    get_settings.cache_clear()
    client = TestClient(create_app())

    expected_missing = [
        "VERTEX_AI_PROJECT_ID",
        "VERTEX_AI_EMBEDDING_LOCATION",
        "VERTEX_AI_GENERATION_LOCATION",
        "FIRESTORE_DATABASE",
        "GCS_BUCKET_NAME",
        "GEMINI_MODEL_NAME",
        "EMBEDDING_MODEL_NAME",
    ]

    for path in ("/ready", "/api/v1/ready"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {
            "status": "not_ready",
            "service": "Insurance GenAI Agent API",
            "environment": "test",
            "version": "0.1.0-test",
            "ready": False,
            "missing_settings": expected_missing,
        }


def test_ready_endpoints_return_ready_when_required_settings_exist(monkeypatch) -> None:
    """Both ready endpoints should report ready when required settings are present."""
    monkeypatch.setenv("APP_NAME", "Insurance GenAI Agent API")
    monkeypatch.setenv("APP_VERSION", "0.1.0-test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("VERTEX_AI_PROJECT_ID", "sample-project")
    monkeypatch.setenv("VERTEX_AI_EMBEDDING_LOCATION", "asia-northeast3")
    monkeypatch.setenv("VERTEX_AI_GENERATION_LOCATION", "global")
    monkeypatch.setenv("FIRESTORE_DATABASE", "sample-database")
    monkeypatch.setenv("GCS_BUCKET_NAME", "sample-bucket")
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-sample")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "embedding-sample")

    get_settings.cache_clear()
    client = TestClient(create_app())

    for path in ("/ready", "/api/v1/ready"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "service": "Insurance GenAI Agent API",
            "environment": "test",
            "version": "0.1.0-test",
            "ready": True,
            "missing_settings": [],
        }


def test_app_startup_logs_runtime_diagnostics(monkeypatch, capsys) -> None:
    """Startup should emit runtime diagnostics useful for Cloud Run failures."""
    monkeypatch.setenv("APP_NAME", "Insurance GenAI Agent API")
    monkeypatch.setenv("APP_VERSION", "0.1.0-test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("PORT", "8080")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    stdout_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    startup_payloads = [json.loads(line) for line in stdout_lines if '"message": "application_starting"' in line]
    assert startup_payloads
    startup_payload = startup_payloads[-1]
    assert startup_payload["port"] == "8080"
    assert startup_payload["environment"] == "test"
    assert startup_payload["ready"] is False
    assert "VERTEX_AI_PROJECT_ID" in startup_payload["missing_settings"]
