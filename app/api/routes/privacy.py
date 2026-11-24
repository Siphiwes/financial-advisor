"""User-controlled export and deletion of personal financial data."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, get_user_for_deletion
from app.schemas.auth import AuthenticatedUser
from app.schemas.privacy import (
    PrivacyDeleteRequest,
    PrivacyDeleteResponse,
    PrivacyExportResponse,
)
from app.services import finance

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
DeletionUser = Annotated[AuthenticatedUser, Depends(get_user_for_deletion)]


@router.get("/audit")
def read_my_audit_events(
    current_user: CurrentUser,
    limit: int = 100,
) -> list[dict]:
    """Return a limited list of this account's data-access and change events."""
    try:
        return finance.list_audit_events(current_user, limit=limit)
    except finance.FinanceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/export", response_model=PrivacyExportResponse)
def export_my_data(current_user: CurrentUser) -> dict:
    """Export the user's application records, even while finance writes are gated."""
    try:
        finance.record_sensitive_access(current_user, "export", "privacy")
        return finance.export_user_data(current_user)
    except finance.FinanceAuditError as exc:
        raise HTTPException(
            status_code=503,
            detail="The export was blocked because its audit event could not be recorded.",
        ) from exc
    except finance.FinanceValidationError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("User data export failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="The account data export could not be completed.",
        ) from exc


@router.delete("/data", response_model=PrivacyDeleteResponse)
def delete_my_data(
    payload: PrivacyDeleteRequest,
    current_user: DeletionUser,
) -> dict:
    """Delete user-owned finance documents after password re-verification."""
    try:
        return finance.delete_user_data_and_account(
            current_user,
            payload.current_password,
        )
    except finance.FinanceAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except finance.FinanceValidationError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except finance.FinanceRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("User data deletion failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail=(
                "The deletion could not be completed. The account remains available "
                "so you can retry. Contact support if the problem continues."
            ),
        ) from exc
