"""Token-protected operational diagnostics."""

import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.config import get_setting
from app.api.dependencies import get_current_user
from app.schemas.auth import AuthenticatedUser
from app.services.diagnostics import list_diagnostic_events
from app.database.cloudant import (
    CloudantConfigurationError,
    get_cloudant_client,
    get_database_name,
    verify_document_round_trip,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["diagnostics"])


def require_diagnostics_token(
    supplied_token: Annotated[
        str | None,
        Header(alias="X-Cloudant-Diagnostics-Token"),
    ] = None,
) -> None:
    """Require a separately managed token before running Cloudant diagnostics."""
    expected_token = get_setting("CLOUDANT_DIAGNOSTICS_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail="Cloudant diagnostics are disabled until configured.",
        )

    if not supplied_token or not hmac.compare_digest(
        supplied_token.encode("utf-8"),
        expected_token.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid diagnostics token.")


@router.get(
    "/health/cloudant",
    dependencies=[Depends(require_diagnostics_token)],
    summary="Check Cloudant database connectivity",
)
def cloudant_health() -> dict:
    """Confirm IAM authentication and read access to the configured database."""
    try:
        client = get_cloudant_client()
        database = get_database_name()
        information = client.get_database_information(db=database).get_result()
    except CloudantConfigurationError as exc:
        logger.warning("Cloudant configuration is incomplete: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Cloudant configuration is incomplete.",
        ) from exc
    except Exception as exc:
        logger.warning("Cloudant connectivity check failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail=(
                "Cloudant connectivity check failed. "
                "Check application logs and IAM permissions."
            ),
        ) from exc

    return {
        "status": "connected",
        "database": database,
        "document_count": information.get("doc_count"),
    }


@router.post(
    "/diagnostics/cloudant/round-trip",
    dependencies=[Depends(require_diagnostics_token)],
    summary="Test Cloudant document create, read and delete access",
)
def cloudant_round_trip() -> dict:
    """Run a temporary, non-financial create/read/delete test against Cloudant."""
    try:
        client = get_cloudant_client()
        database = get_database_name()
        checks = verify_document_round_trip(client, database)
    except CloudantConfigurationError as exc:
        logger.warning("Cloudant configuration is incomplete: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Cloudant configuration is incomplete.",
        ) from exc
    except Exception as exc:
        logger.warning("Cloudant document round-trip failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Cloudant document test failed. Check application logs and IAM permissions.",
        ) from exc

    return {
        "status": "passed",
        "database": database,
        "checks": checks,
        "note": "The temporary diagnostic document was deleted.",
    }



@router.get(
    "/api/v1/diagnostics",
    summary="List recent application errors for the authenticated user",
)
def read_application_diagnostics(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict]:
    """Return recent application diagnostic records without financial payloads."""
    try:
        return list_diagnostic_events(user.id, limit=limit)
    except Exception as exc:
        logger.error("Application diagnostics retrieval failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="System diagnostics are temporarily unavailable because the diagnostic store could not be reached.",
        ) from exc
