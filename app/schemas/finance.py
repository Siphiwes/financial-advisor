"""Validated API models for accounts, transactions, budgets and goals."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

AccountType = Literal["cheque", "savings", "credit_card", "investment", "loan", "other"]
BudgetPeriod = Literal["weekly", "monthly", "quarterly", "yearly"]

class FinancialAccountCreate(BaseModel):
    """Create an account record without collecting online banking credentials."""

    institution: Literal["FNB"] = "FNB"
    display_name: str = Field(min_length=1, max_length=80)
    account_type: AccountType
    currency: str = Field(default="ZAR", pattern=r"^[A-Z]{3}$")
    account_last_four: str = Field(pattern=r"^\d{4}$")

class FinancialAccountUpdate(BaseModel):
    """Fields an account owner may change."""

    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    account_type: AccountType | None = None
    is_active: bool | None = None

class FinancialAccountResponse(BaseModel):
    id: str
    institution: str
    display_name: str
    account_type: AccountType
    currency: str
    account_last_four: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class TransactionCreate(BaseModel):
    """Create a manual transaction using a user-owned account."""

    account_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    transaction_date: date
    description: str = Field(min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=160)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    service_fee: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    balance_after: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    category: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Description cannot be blank.")
        return value.strip()

class TransactionUpdate(BaseModel):
    """User-editable transaction fields, with correction history preserved."""

    transaction_date: date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=160)
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    category: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)

class TransactionResponse(BaseModel):
    id: str
    account_id: str
    transaction_date: date
    description: str
    reference: str | None
    amount: Decimal
    currency: str
    service_fee: Decimal | None
    balance_after: Decimal | None
    category: str | None
    notes: str | None
    source: Literal["manual", "fnb_csv"]
    import_id: str | None
    original: dict
    corrections: list[dict]
    created_at: datetime
    updated_at: datetime

class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    limit: int
    offset: int
    has_more: bool

class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="ZAR", pattern=r"^[A-Z]{3}$")
    period: BudgetPeriod = "monthly"
    start_date: date
    end_date: date | None = None

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, value: date | None, info) -> date | None:
        start_date = info.data.get("start_date")
        if value and start_date and value < start_date:
            raise ValueError("End date cannot be earlier than start date.")
        return value

class BudgetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    period: BudgetPeriod | None = None
    end_date: date | None = None
    is_active: bool | None = None

class BudgetResponse(BaseModel):
    id: str
    name: str
    category: str
    amount: Decimal
    currency: str
    period: BudgetPeriod
    start_date: date
    end_date: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    target_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="ZAR", pattern=r"^[A-Z]{3}$")
    target_date: date | None = None

class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    target_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=2
    )
    target_date: date | None = None
    is_active: bool | None = None

class GoalResponse(BaseModel):
    id: str
    name: str
    description: str | None
    target_amount: Decimal
    currency: str
    target_date: date | None
    saved_amount: Decimal
    contributions: list[dict] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime

class CurrencySummary(BaseModel):
    currency: str
    income: Decimal
    expenses: Decimal
    net_cash_flow: Decimal
    transaction_count: int

class CategorySummary(BaseModel):
    category: str
    currency: str
    expenses: Decimal
    transaction_count: int

class FinancialSummaryResponse(BaseModel):
    from_date: date | None
    to_date: date | None
    currencies: list[CurrencySummary]
    expenses_by_category: list[CategorySummary]
    data_limit_reached: bool = False

class FNBImportCommitResponse(BaseModel):
    import_id: str
    status: Literal["completed", "already_completed"]
    transaction_count: int
    imported_count: int
    duplicate_count: int
    statement_date: date | None
    account_last_four: str
    message: str

CategoryKind = Literal["income", "expense", "transfer"]

class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: CategoryKind

class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: CategoryKind | None = None
    is_active: bool | None = None

class CategoryResponse(BaseModel):
    id: str
    name: str
    kind: CategoryKind
    is_system: bool
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None

class ImportRecordResponse(BaseModel):
    id: str
    source: str
    account_id: str
    status: Literal["processing", "partial", "completed"]
    transaction_count: int
    imported_count: int
    duplicate_count: int
    statement_date: date | None
    created_at: datetime
    updated_at: datetime



class BudgetProgressResponse(BudgetResponse):
    period_start: date
    period_end: date
    spent: Decimal
    remaining: Decimal
    percent_used: Decimal


class GoalContributionCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    transaction_date: date
    direction: Literal["contribution", "withdrawal"] = "contribution"
    notes: str | None = Field(default=None, max_length=500)


class RecurringPaymentCandidate(BaseModel):
    account_id: str
    description: str
    average_amount: Decimal
    currency: str
    occurrence_count: int
    first_seen: date
    last_seen: date
    frequency: Literal["weekly", "monthly", "irregular"]
    confidence: Literal["low", "medium"]
