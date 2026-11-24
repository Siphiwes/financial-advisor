"""Validated request and response models for personal-finance records."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

RecordId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Money = Annotated[Decimal, Field(max_digits=18, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
NonZeroMoney = Annotated[Decimal, Field(ne=0, max_digits=18, decimal_places=2)]


class FinanceRequest(BaseModel):
    """Base request model that rejects fields the API does not recognize."""

    model_config = ConfigDict(extra="forbid")


class FinancialAccountCreate(FinanceRequest):
    institution: Literal["FNB"]
    account_type: Literal["cheque", "savings", "credit", "investment", "other"]
    display_name: Annotated[str, Field(min_length=1, max_length=80)]
    account_last_four: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")] | None = None
    currency: CurrencyCode = "ZAR"


class FinancialAccountUpdate(FinanceRequest):
    display_name: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.display_name is None and self.is_active is None:
            raise ValueError("At least one account field must be supplied.")
        return self


class FinancialAccount(FinanceRequest):
    id: RecordId
    institution: str
    account_type: str
    display_name: str
    account_last_four: str | None
    currency: CurrencyCode
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TransactionCreate(FinanceRequest):
    account_id: RecordId
    transaction_date: date
    description: Annotated[str, Field(min_length=1, max_length=512)]
    reference: Annotated[str, Field(max_length=256)] | None = None
    amount: NonZeroMoney
    currency: CurrencyCode
    service_fee: Money | None = None
    balance: Money | None = None
    category_id: RecordId | None = None
    notes: Annotated[str, Field(max_length=1000)] | None = None

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Transaction description cannot be blank.")
        return value.strip()


class TransactionUpdate(FinanceRequest):
    category_id: RecordId | None = None
    merchant_override: Annotated[str, Field(max_length=160)] | None = None
    notes: Annotated[str, Field(max_length=1000)] | None = None
    is_reviewed: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if all(
            value is None
            for value in (
                self.category_id,
                self.merchant_override,
                self.notes,
                self.is_reviewed,
            )
        ):
            raise ValueError("At least one transaction field must be supplied.")
        return self


class Transaction(FinanceRequest):
    id: RecordId
    account_id: RecordId
    import_id: RecordId | None
    transaction_date: date
    description: str
    reference: str | None
    amount: Money
    currency: CurrencyCode
    service_fee: Money | None
    balance: Money | None
    category_id: RecordId | None
    merchant_override: str | None
    notes: str | None
    source: Literal["manual", "fnb_csv"]
    is_reviewed: bool
    created_at: datetime
    updated_at: datetime


class CategoryCreate(FinanceRequest):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    kind: Literal["income", "expense", "transfer"]
    description: Annotated[str, Field(max_length=300)] | None = None


class CategoryUpdate(FinanceRequest):
    name: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    description: Annotated[str, Field(max_length=300)] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.name is None and self.description is None and self.is_active is None:
            raise ValueError("At least one category field must be supplied.")
        return self


class Category(FinanceRequest):
    id: RecordId
    name: str
    kind: Literal["income", "expense", "transfer"]
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BudgetCreate(FinanceRequest):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    period: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]
    amount: PositiveMoney
    currency: CurrencyCode
    category_id: RecordId | None = None


class BudgetUpdate(FinanceRequest):
    name: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    amount: PositiveMoney | None = None
    category_id: RecordId | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if all(value is None for value in (self.name, self.amount, self.category_id, self.is_active)):
            raise ValueError("At least one budget field must be supplied.")
        return self


class Budget(FinanceRequest):
    id: RecordId
    name: str
    period: str
    amount: PositiveMoney
    currency: CurrencyCode
    category_id: RecordId | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class GoalCreate(FinanceRequest):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    target_amount: PositiveMoney
    currency: CurrencyCode
    target_date: date | None = None


class GoalUpdate(FinanceRequest):
    name: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    target_amount: PositiveMoney | None = None
    target_date: date | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if all(
            value is None
            for value in (self.name, self.target_amount, self.target_date, self.is_active)
        ):
            raise ValueError("At least one goal field must be supplied.")
        return self


class GoalContributionCreate(FinanceRequest):
    amount: PositiveMoney
    contribution_date: date
    note: Annotated[str, Field(max_length=300)] | None = None


class FinancialGoal(FinanceRequest):
    id: RecordId
    name: str
    target_amount: PositiveMoney
    currency: CurrencyCode
    target_date: date | None
    contributed_amount: Money
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PaginatedRecords(FinanceRequest):
    items: list[dict]
    next_bookmark: str | None


class FinancialSummary(FinanceRequest):
    from_date: date
    to_date: date
    currency: CurrencyCode
    income: Money
    expenses: Money
    net_cash_flow: Money
    transaction_count: int
    unclassified_count: int
    category_totals: dict[str, Money]
