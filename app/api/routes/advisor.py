"""Privacy-controlled AI financial question answering."""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.api.routes.finance import financial_summary
from app.core.config import get_setting
from app.database.cloudant import get_cloudant_client, get_database_name
from app.database.scoped import (
    UserScopedDocumentConflictError,
    create_user_scoped_document,
    get_user_scoped_document,
    update_user_scoped_document,
)
from app.integrations.watsonx import (
    WatsonxConfigurationError,
    WatsonxRequestError,
    ask_watsonx,
)
from app.schemas.ai import (
    AIAdvisorResponse,
    AIConsentStatus,
    AIConsentUpdate,
    AIRequest,
)
from app.schemas.auth import AuthenticatedUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["AI financial advisor"])
CONSENT_RECORD_ID = "00000000000000000000000000000001"
CONSENT_DATA_NOTICE = (
    "When enabled, the application sends your question and application-calculated "
    "income, expense, cash-flow and category totals to IBM watsonx.ai. It does not "
    "send bank statement files, account numbers, transaction descriptions or references."
)


def _consent_document(client, database: str, user_id: str) -> dict | None:
    return get_user_scoped_document(
        client, database, user_id, "privacy_settings", CONSENT_RECORD_ID
    )


@router.get("/privacy/ai-consent", response_model=AIConsentStatus)
def get_ai_consent(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client = get_cloudant_client()
    database = get_database_name()
    document = _consent_document(client, database, current_user.id)
    data = document["data"] if document else {}
    return AIConsentStatus(
        consent=data.get("watsonx_aggregate_data_consent", False) is True,
        updated_at=data.get("updated_at"),
        data_sent=CONSENT_DATA_NOTICE,
    )


@router.put("/privacy/ai-consent", response_model=AIConsentStatus)
def update_ai_consent(
    payload: AIConsentUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client = get_cloudant_client()
    database = get_database_name()
    now = datetime.now(timezone.utc).isoformat()
    document = _consent_document(client, database, current_user.id)
    data = {
        **(document["data"] if document else {}),
        "watsonx_aggregate_data_consent": payload.consent,
        "updated_at": now,
    }

    if document is None:
        try:
            create_user_scoped_document(
                client,
                database,
                current_user.id,
                "privacy_settings",
                data,
                record_id=CONSENT_RECORD_ID,
            )
        except UserScopedDocumentConflictError:
            update_user_scoped_document(
                client,
                database,
                current_user.id,
                "privacy_settings",
                CONSENT_RECORD_ID,
                data,
            )
    else:
        update_user_scoped_document(
            client,
            database,
            current_user.id,
            "privacy_settings",
            CONSENT_RECORD_ID,
            data,
        )

    return AIConsentStatus(
        consent=payload.consent,
        updated_at=now,
        data_sent=CONSENT_DATA_NOTICE,
    )


@router.post("/advisor/ask", response_model=AIAdvisorResponse)
def ask_financial_advisor(
    payload: AIRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    if payload.from_date > payload.to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date.")

    if (get_setting("AI_ADVISOR_ENABLED", "false") or "false").casefold() != "true":
        raise HTTPException(status_code=503, detail="The AI advisor is not enabled.")
    if (
        get_setting("AI_DATA_PROCESSING_APPROVED", "false") or "false"
    ).casefold() != "true":
        raise HTTPException(
            status_code=503,
            detail="External AI data processing has not been approved by the application operator.",
        )

    client = get_cloudant_client()
    database = get_database_name()
    consent = _consent_document(client, database, current_user.id)
    if not consent or consent["data"].get("watsonx_aggregate_data_consent") is not True:
        raise HTTPException(
            status_code=403,
            detail="Explicit consent is required before sending financial summaries to IBM watsonx.ai.",
        )

    summary = financial_summary(
        current_user,
        payload.from_date,
        payload.to_date,
        payload.currency,
    )
    verified_data = summary.model_dump(mode="json")
    try:
        answer, model_id = ask_watsonx(payload.question, verified_data)
    except WatsonxConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="watsonx.ai is not configured.",
        ) from exc
    except WatsonxRequestError as exc:
        logger.warning("watsonx.ai request failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The AI advisor could not complete the request.",
        ) from exc

    return AIAdvisorResponse(
        answer=answer,
        model=model_id,
        data_scope="User question and application-calculated financial aggregates only.",
        disclaimer=(
            "This is educational information, not regulated financial advice. "
            "Verify important decisions against your bank statements and circumstances."
        ),
    )
