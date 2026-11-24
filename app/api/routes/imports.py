"""Authenticated statement-import preview endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import get_current_user
from app.schemas.auth import AuthenticatedUser
from app.schemas.imports import FNBImportPreview, FNBTransactionPreview
from app.services.fnb_csv import FNBCSVValidationError, MAX_CSV_BYTES, parse_fnb_csv

router = APIRouter(prefix="/imports", tags=["statement imports"])
PREVIEW_TRANSACTION_LIMIT = 10


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
        if not file.filename or not file.filename.casefold().endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Upload an FNB CSV file with a .csv extension.",
            )

        content = await file.read(MAX_CSV_BYTES + 1)
        if len(content) > MAX_CSV_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The uploaded CSV file exceeds the 20 MB limit.",
            )

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
