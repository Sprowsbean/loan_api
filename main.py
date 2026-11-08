"""Loan Application Service: stores loan applications and scores their default risk."""
import hmac
import os

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from schemas import Application, ApplicationCreate, ApplicationPage, Error, LoanFeatures, Prediction

ml = {}            # filled at start-up: {"predict": ..., "version": ..., "features": [...]}
APPLICATIONS = {}  # in-memory store; resets when the server restarts
MODEL_PATH = os.getenv("MODEL_PATH", "model.joblib")
MODEL_NAME = os.getenv("MODEL_NAME", "loan-default")
MODEL_ALIAS = os.getenv("MODEL_ALIAS", "champion")
FEATURES = ["amount_usd", "term_months", "monthly_income_usd", "previous_loans", "late_payments"]
GIT_SHA = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_SHA", "unknown")  # set by Render at run time
API_KEY = os.getenv("API_KEY")  # unset locally and in CI, so /api/ stays open there; set in Render in production


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("MLFLOW_TRACKING_URI"):
        # Registry mode: MLFLOW_TRACKING_URI says where the registry is; load whichever version the alias points to
        import mlflow
        from mlflow import MlflowClient
        model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{MODEL_ALIAS}")
        ml["predict"] = lambda X: float(model.predict(X)[0, 1])  # pyfunc returns predict_proba output
        ml["version"] = MlflowClient().get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS).version
    else:
        # File mode (CI and production): the model file baked into the image
        saved = joblib.load(MODEL_PATH)
        ml["predict"] = lambda X: float(saved["model"].predict_proba(X)[0, 1])
        ml["version"] = saved["version"]
    ml["features"] = FEATURES
    yield
    ml.clear()


app = FastAPI(title="Loan Application Service", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if API_KEY and request.url.path.startswith("/api/"):
        supplied = request.headers.get("x-api-key", "")
        # compare_digest takes the same time whether or not the characters match
        if not hmac.compare_digest(supplied.encode(), API_KEY.encode()):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


def score(features: LoanFeatures) -> Prediction:
    X = pd.DataFrame([features.model_dump()])[ml["features"]]
    probability = ml["predict"](X)
    band = "low" if probability < 0.2 else "medium" if probability < 0.5 else "high"
    return Prediction(default_probability=round(1 - probability, 3), risk_band=band, model_version=ml["version"])


@app.get("/health")
def health():
    return {"status": "ok", "model_version": ml.get("version"), "sha": GIT_SHA}


@app.post("/api/v1/predictions", response_model=Prediction)
def predict(features: LoanFeatures):
    return score(features)


@app.post("/api/v1/applications", response_model=Application, status_code=201)
def create_application(body: ApplicationCreate, response: Response):
    new = Application(id=7781 + len(APPLICATIONS), status="pending", submitted_at=datetime.now(timezone.utc),
                      prediction=score(body), **body.model_dump())
    APPLICATIONS[new.id] = new
    response.headers["Location"] = f"/api/v1/applications/{new.id}"
    return new


@app.get("/api/v1/applications", response_model=ApplicationPage)
def list_applications(status: Literal["pending", "approved", "rejected"] | None = None,
                      limit: int = Query(20, ge=1, le=100), cursor: int | None = None):
    matches = [a for a in APPLICATIONS.values()
               if (status is None or a.status == status) and (cursor is None or a.id > cursor)]
    page = matches[:limit]
    return ApplicationPage(items=page, next_cursor=page[-1].id if len(matches) > limit else None)


@app.get("/api/v1/applications/{application_id}", response_model=Application,
         responses={404: {"model": Error, "description": "No application with this id"}})
def get_application(application_id: int):
    if application_id not in APPLICATIONS:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return APPLICATIONS[application_id]
