"""Statement-import preview response models."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class FNBTransactionPreview(BaseModel):
    """A transaction row returned for inspection, not stored."""

    effective_date: date
    description: str
    reference: str | None
    service_fee: Decimal | None
    amount: Decimal
    balance: Decimal | None


class FNBImportPreview(BaseModel):
    """Metadata and a bounded preview of an uploaded FNB statement."""

    bank: Literal["FNB"] = "FNB"
    source_format: Literal["FNB CSV"] = "FNB CSV"
    statement_date: date | None
    account_last_four: str | None
    opening_balance: Decimal | None
    closing_balance: Decimal | None
    transaction_count: int = Field(ge=1)
    preview_limit: int = Field(ge=1)
    transactions: list[FNBTransactionPreview]
    persisted: Literal[False] = False
    message: str
