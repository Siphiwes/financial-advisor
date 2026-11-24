"""Authenticated statement-import preview endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.dependencies import get_current_user, require_financial_data_enabled
from app.schemas.auth import AuthenticatedUser
from app.schemas.finance import FNBImportCommitResponse, ImportRecordResponse
from app.schemas.imports import FNBImportPreview, FNBTransactionPreview
from app.services import finance
from app.services.finance import (
    FinanceRecordNotFoundError,
    FinanceValidationError,
    commit_fnb_import,
    get_import_record,
    list_import_records,
)
from app.services.fnb_csv import MAX_CSV_BYTES, FNBCSVValidationError, parse_fnb_csv
from app.services.fnb_pdf import FNBPDFValidationError, parse_fnb_pdf

router = APIRouter(prefix="/imports", tags=["statement imports"])
PREVIEW_TRANSACTION_LIMIT = 10_000

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
    finance.record_sensitive_access(_current_user, "preview", "fnb_statement")
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


@router.post(
    "/fnb/pdf/preview",
    response_model=FNBImportPreview,
    summary="Preview an FNB South Africa PDF statement",
    status_code=status.HTTP_200_OK,
)
async def preview_fnb_pdf(
    _current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    file: Annotated[
        UploadFile,
        File(description="Unencrypted, text-based FNB PDF statement"),
    ],
) -> FNBImportPreview:
    """Extract a supported FNB PDF statement in memory without persisting it."""
    finance.record_sensitive_access(_current_user, "preview", "fnb_statement")
    try:
        if not file.filename or not file.filename.casefold().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Upload an FNB PDF file with a .pdf extension.",
            )
        content = await file.read(MAX_CSV_BYTES + 1)
        if len(content) > MAX_CSV_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The uploaded PDF file exceeds the 20 MB limit.",
            )
        statement = parse_fnb_pdf(content)
    except FNBPDFValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()

    return FNBImportPreview(
        source_format="FNB PDF",
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
            for transaction in statement.transactions[:PREVIEW_TRANSACTION_LIMIT]
        ],
        message=(
            "PDF preview only. The original PDF and extracted transactions were not "
            "saved to Cloudant. Confirm the dates and amounts before any future import."
        ),
    )

@router.post(
    "/fnb/csv/confirm",
    response_model=FNBImportCommitResponse,
    summary="Confirm and import an FNB CSV into the selected account",
    dependencies=[Depends(require_financial_data_enabled)],
)
async def confirm_fnb_csv_import(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    account_id: Annotated[
        str,
        Form(description="ID of the authenticated user's FNB account"),
    ],
    consent: Annotated[
        bool,
        Form(description="Must be true to confirm persistent transaction storage"),
    ],
    file: Annotated[
        UploadFile,
        File(description="FNB transaction-history export in CSV format"),
    ],
) -> FNBImportCommitResponse:
    """Persist a confirmed FNB export after validation and account matching."""
    try:
        if consent is not True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit confirmation is required before importing transactions.",
            )
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

    try:
        return commit_fnb_import(current_user, account_id, statement, content)
    except FinanceRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail="The selected account was not found.") from exc
    except FinanceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post(
    "/fnb/pdf/confirm",
    response_model=FNBImportCommitResponse,
    summary="Confirm and import an FNB PDF statement into the selected account",
    dependencies=[Depends(require_financial_data_enabled)],
)
async def confirm_fnb_pdf_import(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    account_id: Annotated[
        str,
        Form(description="ID of the authenticated user's FNB account"),
    ],
    consent: Annotated[
        bool,
        Form(description="Must be true to confirm persistent transaction storage"),
    ],
    file: Annotated[
        UploadFile,
        File(description="FNB transaction-history PDF statement"),
    ],
) -> FNBImportCommitResponse:
    """Persist a confirmed FNB PDF after parsing and account matching."""
    try:
        if consent is not True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit confirmation is required before importing transactions.",
            )
        if not file.filename or not file.filename.casefold().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Upload an FNB PDF file with a .pdf extension.",
            )
        content = await file.read(MAX_CSV_BYTES + 1)
        if len(content) > MAX_CSV_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The uploaded PDF file exceeds the 20 MB limit.",
            )
        statement = parse_fnb_pdf(content)
    except FNBPDFValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()

    try:
        return commit_fnb_import(
            current_user,
            account_id,
            statement,
            content,
            source_format="FNB_PDF",
        )
    except FinanceRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail="The selected account was not found.") from exc
    except FinanceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "",
    response_model=list[ImportRecordResponse],
    dependencies=[Depends(require_financial_data_enabled)],
)
def read_import_history(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[dict]:
    finance.record_sensitive_access(current_user, "read", "import_history")
    return list_import_records(current_user)

@router.get(
    "/{import_id}",
    response_model=ImportRecordResponse,
    dependencies=[Depends(require_financial_data_enabled)],
)
def read_import(
    import_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict:
    finance.record_sensitive_access(current_user, "read", "import_record")
    try:
        return get_import_record(current_user, import_id)
    except FinanceRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail="The requested import was not found.") from exc
