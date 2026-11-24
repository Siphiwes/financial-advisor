"""Consent-based AI financial advisor endpoint."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user, require_financial_ai_enabled
from app.integrations.watsonx import (
    WatsonxConfigurationError,
    WatsonxProviderError,
    ask_financial_advisor,
)
from app.schemas.advisor import AdvisorChatRequest, AdvisorChatResponse
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
    """Send a question and a bounded aggregate summary to IBM watsonx.ai."""
    if payload.consent_to_share_summary is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Explicit consent is required before an aggregated financial summary "
                "and your question are sent to IBM watsonx.ai."
            ),
        )

    try:
        summary = finance.financial_summary(
            current_user,
            from_date=payload.from_date,
            to_date=payload.to_date,
        )
    except finance.FinanceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    summary_data = summary.model_dump(mode="json")
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
            "Aggregated income, expenses, transfers and net cash flow by currency",
            "Aggregated expenses by category",
            "The selected date range",
        ],
    )
