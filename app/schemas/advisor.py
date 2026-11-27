"""Request and response schemas for the AI financial advisor."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AdvisorChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    consent_to_share_all_financial_records: bool = False
    from_date: date | None = None
    to_date: date | None = None

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Enter a question.")
        return cleaned

    @field_validator("to_date")
    @classmethod
    def validate_date_range(cls, value: date | None, info) -> date | None:
        from_date = info.data.get("from_date")
        if value and from_date and value < from_date:
            raise ValueError("End date cannot be earlier than start date.")
        return value


class AdvisorChatResponse(BaseModel):
    provider: Literal["IBM watsonx.ai"] = "IBM watsonx.ai"
    model_id: str
    answer: str
    data_shared: list[str]



class TransactionCategorySuggestionRequest(BaseModel):
    consent_to_share_transaction: bool = False


class TransactionCategorySuggestionResponse(BaseModel):
    provider: Literal["IBM watsonx.ai"] = "IBM watsonx.ai"
    model_id: str
    transaction_id: str
    suggested_category: str
    explanation: str = Field(min_length=1, max_length=500)
    applied: Literal[False] = False
    data_shared: list[str]


class BulkTransactionCategorySuggestionRequest(BaseModel):
    transaction_ids: list[str] = Field(min_length=1, max_length=50)
    consent_to_share_transactions: bool = False

    @field_validator("transaction_ids")
    @classmethod
    def validate_transaction_ids(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("Transaction IDs cannot be blank.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Select each transaction only once.")
        return cleaned


class BulkTransactionCategorySuggestionItem(BaseModel):
    transaction_id: str
    suggested_category: str
    explanation: str = Field(min_length=1, max_length=500)


class BulkTransactionCategorySuggestionResponse(BaseModel):
    provider: Literal["IBM watsonx.ai"] = "IBM watsonx.ai"
    model_id: str
    suggestions: list[BulkTransactionCategorySuggestionItem]
    data_shared: list[str]
