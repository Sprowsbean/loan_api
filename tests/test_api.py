"""Run with: python train.py && pytest -v"""
import pytest
from fastapi.testclient import TestClient

import main
from main import APPLICATIONS, app

GOOD = {"amount_usd": 1500, "term_months": 12, "monthly_income_usd": 350.0, "previous_loans": 1, "late_payments": 0}


@pytest.fixture
def client():
    APPLICATIONS.clear()
    with TestClient(app) as c:  # "with" runs the lifespan, so the model is loaded
        yield c


def test_health_reports_model_version(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["model_version"]  # from the model file, or the registry when MLFLOW_TRACKING_URI is set
    assert "sha" in body          # the pipeline compares this with the commit it just deployed

def test_prediction_is_a_probability(client):
    body = client.post("/api/v1/predictions", json=GOOD).json()
    assert 0 <= body["default_probability"] <= 1
    assert body["risk_band"] in {"low", "medium", "high"}


def test_amount_above_limit_is_rejected(client):
    assert client.post("/api/v1/predictions", json={**GOOD, "amount_usd": 9000}).status_code == 422


def test_create_and_read_application(client):
    created = client.post("/api/v1/applications", json={**GOOD, "borrower_id": 1042})
    assert created.status_code == 201
    app_id = created.json()["id"]
    assert client.get(f"/api/v1/applications/{app_id}").json()["borrower_id"] == 1042


def test_missing_application_is_404(client):
    assert client.get("/api/v1/applications/99999").status_code == 404


def test_api_rejects_missing_or_wrong_key(client, monkeypatch):
    monkeypatch.setattr(main, "API_KEY", "s3cret")
    assert client.get("/api/v1/applications").status_code == 401
    assert client.get("/api/v1/applications", headers={"X-API-Key": "wrong"}).status_code == 401


def test_api_accepts_right_key_and_health_stays_open(client, monkeypatch):
    monkeypatch.setattr(main, "API_KEY", "s3cret")
    assert client.get("/api/v1/applications", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert client.get("/health").status_code == 200


def test_create_sets_location_header_and_submitted_at(client):
    created = client.post("/api/v1/applications", json={**GOOD, "borrower_id": 1})
    assert created.headers["location"] == f"/api/v1/applications/{created.json()['id']}"
    assert created.json()["submitted_at"]


def test_list_returns_a_page(client):
    assert client.get("/api/v1/applications").json() == {"items": [], "next_cursor": None}


def test_list_limit_and_cursor_walk_through_all_applications(client):
    for n in range(3):
        client.post("/api/v1/applications", json={**GOOD, "borrower_id": n + 1})
    first = client.get("/api/v1/applications", params={"limit": 2}).json()
    assert len(first["items"]) == 2 and first["next_cursor"] is not None
    second = client.get("/api/v1/applications", params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 1 and second["next_cursor"] is None


def test_list_filters_by_status(client):
    client.post("/api/v1/applications", json={**GOOD, "borrower_id": 1})
    assert len(client.get("/api/v1/applications", params={"status": "pending"}).json()["items"]) == 1
    assert client.get("/api/v1/applications", params={"status": "approved"}).json()["items"] == []


def test_list_limit_above_100_is_rejected(client):
    assert client.get("/api/v1/applications", params={"limit": 101}).status_code == 422


def test_openapi_documents_the_404(client):
    spec = client.get("/openapi.json").json()
    assert "404" in spec["paths"]["/api/v1/applications/{application_id}"]["get"]["responses"]
