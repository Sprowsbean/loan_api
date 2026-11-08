"""Request and response shapes for the loan service (the contract from Module 2)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoanFeatures(BaseModel):
    amount_usd: int = Field(ge=100, le=5000, examples=[1500])
    term_months: Literal[3, 6, 12, 18, 24] = Field(examples=[12])
    monthly_income_usd: float = Field(gt=0, examples=[350.0])
    previous_loans: int = Field(ge=0, examples=[1])
    late_payments: int = Field(ge=0, examples=[0])


class Prediction(BaseModel):
    default_probability: float
    risk_band: Literal["low", "medium", "high"]
    model_version: str


class ApplicationCreate(LoanFeatures):
    borrower_id: int = Field(ge=1, examples=[1042])


class Application(ApplicationCreate):
    id: int
    status: Literal["pending", "approved", "rejected"]
    submitted_at: datetime
    prediction: Prediction


class ApplicationPage(BaseModel):
    items: list[Application]
    next_cursor: int | None = None  # pass it back as ?cursor= to get the next page


class Error(BaseModel):
    detail: str
