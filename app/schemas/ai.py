"""Request and response models for privacy-controlled AI assistance."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class AIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Annotated[str, Field(min_length=5, max_length=1200)]
    from_date: date
    to_date: date
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] = "ZAR"


class AIConsentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent: bool


class AIConsentStatus(BaseModel):
    consent: bool
    updated_at: str | None
    data_sent: str


class AIAdvisorResponse(BaseModel):
    answer: str
    model: str
    data_scope: str
    disclaimer: str
