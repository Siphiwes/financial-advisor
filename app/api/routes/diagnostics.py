"""Token-protected operational diagnostics."""

import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import get_setting
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
            detail="Cloudant connectivity check failed. Check application logs and IAM permissions.",
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
