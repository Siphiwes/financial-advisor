"""Authenticated FNB statement preview and confirmation endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.api.dependencies import get_current_user
from app.database.cloudant import get_cloudant_client, get_database_name
from app.database.scoped import (
    get_user_scoped_document,
    list_user_scoped_documents,
)
from app.schemas.auth import AuthenticatedUser
from app.schemas.imports import (
    FNBImportConfirmation,
    FNBImportPreview,
    FNBTransactionPreview,
)
from app.services.fnb_csv import (
    MAX_CSV_BYTES,
    FNBCSVValidationError,
    parse_fnb_csv,
)
from app.services.fnb_import import (
    FNBImportAlreadyRunningError,
    confirm_fnb_csv_import,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/imports", tags=["statement imports"])
PREVIEW_TRANSACTION_LIMIT = 10


def _require_csv_filename(file: UploadFile) -> None:
    if not file.filename or not file.filename.casefold().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload an FNB CSV file with a .csv extension.",
        )


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The uploaded CSV file exceeds the 20 MB limit.",
        )
    return content


@router.post(
    "/fnb/csv/preview",
    response_model=FNBImportPreview,
    summary="Preview an FNB South Africa transaction-history CSV",
    status_code=status.HTTP_200_OK,
)
async def preview_fnb_csv(
    _current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    file: Annotated[
        UploadFile,
        File(description="FNB transaction-history export in CSV format"),
    ],
) -> FNBImportPreview:
    """Parse an authenticated FNB CSV upload in memory without persisting it."""
    try:
        _require_csv_filename(file)
        content = await _read_upload(file)
        statement = parse_fnb_csv(content)
    except FNBCSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()

    preview_rows = statement.transactions[:PREVIEW_TRANSACTION_LIMIT]
    return FNBImportPreview(
        statement_date=statement.statement_date,
        account_last_four=statement.account_last_four,
        opening_balance=statement.opening_balance,
        closing_balance=statement.closing_balance,
        transaction_count=len(statement.transactions),
        preview_limit=PREVIEW_TRANSACTION_LIMIT,
        transactions=[
            FNBTransactionPreview(
                effective_date=transaction.effective_date,
                description=transaction.description,
                reference=transaction.reference,
                service_fee=transaction.service_fee,
                amount=transaction.amount,
                balance=transaction.balance,
            )
            for transaction in preview_rows
        ],
        message=(
            "Preview only. The uploaded statement and its transactions were not "
            "saved to Cloudant."
        ),
    )


@router.post(
    "/fnb/csv/confirm",
    response_model=FNBImportConfirmation,
    summary="Confirm and securely import an FNB statement",
    status_code=status.HTTP_201_CREATED,
)
async def confirm_fnb_csv(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    account_id: Annotated[str, Form()],
    file: Annotated[
        UploadFile,
        File(description="The same FNB CSV reviewed in the preview step"),
    ],
) -> FNBImportConfirmation:
    """Persist transactions after the authenticated account holder confirms import."""
    try:
        _require_csv_filename(file)
        content = await _read_upload(file)
        client = get_cloudant_client()
        database = get_database_name()
        account_document = get_user_scoped_document(
            client,
            database,
            current_user.id,
            "accounts",
            account_id,
        )
        if account_document is None:
            raise HTTPException(status_code=404, detail="The financial account was not found.")
        if account_document["data"].get("is_active") is not True:
            raise HTTPException(status_code=409, detail="The financial account is inactive.")

        result = confirm_fnb_csv_import(
            client,
            database,
            current_user.id,
            account_document,
            content,
        )
        return FNBImportConfirmation(**result)
    except HTTPException:
        raise
    except FNBCSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except FNBImportAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This statement import is already being processed.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.warning("FNB statement import failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The FNB statement could not be imported. "
                "Check the import status before retrying."
            ),
        ) from exc
    finally:
        await file.close()


@router.get("/fnb/imports", response_model=dict, summary="List FNB statement imports")
def list_fnb_imports(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    bookmark: str | None = None,
):
    try:
        result = list_user_scoped_documents(
            get_cloudant_client(),
            get_database_name(),
            current_user.id,
            "imports",
            limit=limit,
            bookmark=bookmark,
            filters={"data.bank": "FNB"},
        )
    except Exception as exc:
        logger.warning("FNB import history lookup failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Import history could not be retrieved.",
        ) from exc

    return {
        "items": [
            {"id": document["record_id"], **document["data"]}
            for document in result["documents"]
        ],
        "next_bookmark": result.get("bookmark"),
    }
