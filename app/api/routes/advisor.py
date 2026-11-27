"""Consent-based AI financial advisor endpoint."""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user, require_financial_ai_enabled
from app.integrations.watsonx import (
    WatsonxConfigurationError,
    WatsonxProviderError,
    ask_financial_advisor,
)
from app.schemas.advisor import (
    AdvisorChatRequest,
    AdvisorChatResponse,
    BulkTransactionCategorySuggestionRequest,
    BulkTransactionCategorySuggestionResponse,
    TransactionCategorySuggestionRequest,
    TransactionCategorySuggestionResponse,
)
from app.schemas.auth import AuthenticatedUser
from app.services import finance

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/advisor",
    tags=["AI financial advisor"],
    dependencies=[Depends(require_financial_ai_enabled)],
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


@router.post(
    "/chat",
    response_model=AdvisorChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask the AI advisor using an explicitly shared financial summary",
)
async def chat_with_advisor(
    payload: AdvisorChatRequest,
    current_user: CurrentUser,
) -> AdvisorChatResponse:
    """Send a question and the complete consented financial records to IBM watsonx.ai."""
    if payload.consent_to_share_all_financial_records is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Explicit consent is required before your complete saved financial records "
                "and question are sent to IBM watsonx.ai."
            ),
        )

    finance.record_sensitive_access(current_user, "ai_summary_request", "advisor")
    try:
        summary = finance.full_financial_context(current_user)
        if payload.from_date or payload.to_date:
            summary["financial_summary"] = finance.financial_summary(
                current_user,
                from_date=payload.from_date,
                to_date=payload.to_date,
            ).model_dump(mode="json")
    except finance.FinanceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    summary_data = summary
    try:
        answer, model_id = await ask_financial_advisor(
            payload.question,
            summary_data,
        )
    except WatsonxConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="IBM watsonx.ai is not configured.",
        ) from exc
    except WatsonxProviderError as exc:
        logger.warning("watsonx.ai request failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The AI advisor could not complete the request. Try again later.",
        ) from exc

    return AdvisorChatResponse(
        model_id=model_id,
        answer=answer,
        data_shared=[
            "Your question",
            "All saved account records, including account identifiers and stored account numbers",
            "All saved transactions, including descriptions, references, amounts, dates, "
            "account IDs and original import fields",
            "All saved categories, budgets, goals and debt records",
            "Calculated income, expense, cash-flow and debt summaries",
        ],
    )



@router.post(
    "/transactions/{transaction_id}/suggest-category",
    response_model=TransactionCategorySuggestionResponse,
    summary="Suggest a category for one transaction after explicit data-sharing consent",
)
async def suggest_transaction_category(
    transaction_id: str,
    payload: TransactionCategorySuggestionRequest,
    current_user: CurrentUser,
) -> TransactionCategorySuggestionResponse:
    """Send only one user-selected transaction and allowed category names to AI."""
    if payload.consent_to_share_transaction is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Explicit consent is required before the selected transaction, including its "
                "description, reference, account identifier and stored fields, is sent to "
                "IBM watsonx.ai."
            ),
        )

    finance.record_sensitive_access(current_user, "ai_category_request", "advisor")
    try:
        transaction = finance.get_transaction(current_user, transaction_id)
        categories = finance.list_categories(current_user)
    except finance.FinanceRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail="The transaction was not found.") from exc

    allowed_categories = [
        {"name": item["name"], "kind": item["kind"]}
        for item in categories
        if item.get("is_active", True)
    ]
    if not allowed_categories:
        raise HTTPException(status_code=422, detail="No active categories are available.")

    approved_transaction = dict(transaction)
    try:
        approved_transaction["account"] = finance.get_financial_account(
            current_user.id,
            transaction["account_id"],
            active=False,
        )
    except finance.FinanceRecordNotFoundError:
        approved_transaction["account"] = None
    question = (
        "Choose the single best category for this transaction from the allowed "
        "categories in the supplied data. Return only a JSON object with two keys: "
        "category (exactly one allowed category name) and explanation (a short "
        "reason based only on the supplied transaction fields). Do not invent "
        "merchant information or other facts."
    )
    shared_data = {
        "selected_transaction": approved_transaction,
        "allowed_categories": allowed_categories,
    }

    try:
        answer, model_id = await ask_financial_advisor(question, shared_data)
    except WatsonxConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="IBM watsonx.ai is not configured.",
        ) from exc
    except WatsonxProviderError as exc:
        logger.warning("watsonx.ai category suggestion failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The AI category suggestion could not be completed.",
        ) from exc

    try:
        suggestion = json.loads(answer.strip())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="The AI advisor returned an invalid category suggestion.",
        ) from exc

    selected_category = suggestion.get("category") if isinstance(suggestion, dict) else None
    explanation = suggestion.get("explanation") if isinstance(suggestion, dict) else None
    allowed_names = {item["name"] for item in allowed_categories}
    if selected_category not in allowed_names or not isinstance(explanation, str):
        raise HTTPException(
            status_code=502,
            detail="The AI advisor returned a category outside the allowed list.",
        )

    return TransactionCategorySuggestionResponse(
        model_id=model_id,
        transaction_id=transaction_id,
        suggested_category=selected_category,
        explanation=explanation.strip()[:500],
        applied=False,
        data_shared=[
            "All stored fields for the selected transaction, including description, "
            "reference and account identifier",
            "The associated stored account record, including its account identifier",
            "Available category names and types",
        ],
    )



@router.post(
    "/transactions/suggest-categories",
    response_model=BulkTransactionCategorySuggestionResponse,
    summary="Suggest categories for multiple selected transactions after explicit consent",
)
async def suggest_transaction_categories(
    payload: BulkTransactionCategorySuggestionRequest,
    current_user: CurrentUser,
) -> BulkTransactionCategorySuggestionResponse:
    """Send only the selected transactions and allowed category names to AI."""
    if payload.consent_to_share_transactions is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Explicit consent is required before the selected transactions, including "
                "their descriptions, references, account identifiers and stored fields, "
                "are sent to IBM watsonx.ai."
            ),
        )

    finance.record_sensitive_access(current_user, "ai_bulk_category_request", "advisor")
    transactions = []
    try:
        categories = finance.list_categories(current_user)
        for transaction_id in payload.transaction_ids:
            transaction = finance.get_transaction(current_user, transaction_id)
            approved_transaction = dict(transaction)
            try:
                approved_transaction["account"] = finance.get_financial_account(
                    current_user.id,
                    transaction["account_id"],
                    active=False,
                )
            except finance.FinanceRecordNotFoundError:
                approved_transaction["account"] = None
            transactions.append(approved_transaction)
    except finance.FinanceRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="One or more selected transactions could not be found.",
        ) from exc

    allowed_categories = [
        {"name": item["name"], "kind": item["kind"]}
        for item in categories
        if item.get("is_active", True)
    ]
    if not allowed_categories:
        raise HTTPException(status_code=422, detail="No active categories are available.")

    expected_ids = {item["id"] for item in transactions}
    question = (
        "Categorise every supplied transaction independently. For each transaction, "
        "choose exactly one category from allowed_categories. Return only a JSON object "
        "with one key named suggestions. Its value must be an array containing exactly "
        "one object per supplied transaction. Each object must contain transaction_id "
        "(copied exactly from the supplied transaction), category (an exact allowed "
        "category name), and explanation (a short reason based only on the supplied "
        "transaction fields). Do not omit, duplicate or add transaction IDs. Do not "
        "invent merchant information or other facts."
    )
    shared_data = {
        "selected_transactions": transactions,
        "allowed_categories": allowed_categories,
    }

    try:
        answer, model_id = await ask_financial_advisor(question, shared_data)
    except WatsonxConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="IBM watsonx.ai is not configured.",
        ) from exc
    except WatsonxProviderError as exc:
        logger.warning("watsonx.ai bulk category suggestion failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The AI category suggestions could not be completed.",
        ) from exc

    try:
        result = json.loads(answer.strip())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="The AI advisor returned invalid category suggestions.",
        ) from exc

    raw_suggestions = result.get("suggestions") if isinstance(result, dict) else None
    if not isinstance(raw_suggestions, list):
        raise HTTPException(
            status_code=502,
            detail="The AI advisor returned an invalid suggestions list.",
        )

    allowed_names = {item["name"] for item in allowed_categories}
    suggestions = []
    returned_ids = set()
    for item in raw_suggestions:
        if not isinstance(item, dict):
            raise HTTPException(status_code=502, detail="The AI advisor returned an invalid suggestion.")
        transaction_id = item.get("transaction_id")
        category = item.get("category")
        explanation = item.get("explanation")
        if (
            transaction_id not in expected_ids
            or transaction_id in returned_ids
            or category not in allowed_names
            or not isinstance(explanation, str)
            or not explanation.strip()
        ):
            raise HTTPException(
                status_code=502,
                detail="The AI advisor returned an invalid or unsupported category suggestion.",
            )
        returned_ids.add(transaction_id)
        suggestions.append({
            "transaction_id": transaction_id,
            "suggested_category": category,
            "explanation": explanation.strip()[:500],
        })

    if returned_ids != expected_ids:
        raise HTTPException(
            status_code=502,
            detail="The AI advisor did not return a suggestion for every selected transaction.",
        )

    return BulkTransactionCategorySuggestionResponse(
        model_id=model_id,
        suggestions=suggestions,
        data_shared=[
            "All stored fields for the selected transactions, including descriptions, "
            "references and account identifiers",
            "Associated stored account records for the selected transactions",
            "Available category names and types",
        ],
    )
