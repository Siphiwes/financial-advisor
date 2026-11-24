"""In-memory parser for text-based FNB South Africa PDF statements.

The original PDF is never persisted. Transaction rows are extracted from the
statement's text layer and normalized for preview or explicit import confirmation.
"""

import io
import re
from datetime import date
from decimal import Decimal

import pdfplumber

from app.services.fnb_csv import (
    MAX_CSV_BYTES,
    MAX_TRANSACTIONS,
    FNBCSVValidationError,
    FNBStatement,
    FNBTransaction,
    _parse_date,
    _parse_decimal,
)

MAX_PDF_PAGES = 100

_TRANSACTION_ROW = re.compile(
    r"^(?P<date>\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<service_fee>[0-9,]+\.\d{2})\s+"
    r"(?P<amount>[+-]?[0-9,]+\.\d{2})\s+"
    r"(?P<amount_direction>DR|CR)\s+"
    r"(?P<balance>[0-9,]+\.\d{2})\s+"
    r"(?P<balance_direction>DR|CR)$",
    re.IGNORECASE,
)
_DATE_PREFIX = re.compile(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\b")
_STATEMENT_DATE = re.compile(r"\bDate:\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})")
_ACCOUNT_NUMBER = re.compile(r"Selected Account:\s*([0-9 ]+)", re.IGNORECASE)
_CURRENT_BALANCE = re.compile(
    r"Current Balance:\s*([0-9,]+\.\d{2})\s+(CR|DR)", re.IGNORECASE
)
_IGNORED_PREFIXES = (
    "Printed ",
    "info@",
    "Address:",
    "Tel:",
    "Transaction History",
    "Date Description",
    "Date:",
    "Nickname:",
    "Selected Account:",
    "Available Balance:",
    "Current Balance:",
    "First National Bank",
    "An Authorised",
    "P O Box",
    "Reg. No.",
    "Registered Financial Services",
    "Registered Credit Provider",
    "©",
)


class FNBPDFValidationError(ValueError):
    """Raised when a PDF is unreadable or its transaction layout is unsupported."""


def _parse_pdf_date(value: str) -> date:
    try:
        return _parse_date(value)
    except FNBCSVValidationError as exc:
        raise FNBPDFValidationError(str(exc)) from exc


def _signed_amount(value: str, direction: str) -> Decimal:
    try:
        amount = _parse_decimal(value, required=True)
    except FNBCSVValidationError as exc:
        raise FNBPDFValidationError(str(exc)) from exc
    if amount is None:
        raise FNBPDFValidationError("A PDF transaction is missing its amount.")
    return -abs(amount) if direction.upper() == "DR" else abs(amount)


def _ignored_line(line: str) -> bool:
    return not line or line == "." or line.startswith(_IGNORED_PREFIXES)


def parse_fnb_pdf(content: bytes) -> FNBStatement:
    """Extract an FNB PDF statement in memory without storing the source document."""
    if not content:
        raise FNBPDFValidationError("The uploaded PDF file is empty.")
    if len(content) > MAX_CSV_BYTES:
        raise FNBPDFValidationError("The uploaded PDF file exceeds the 20 MB limit.")
    if not content.startswith(b"%PDF-"):
        raise FNBPDFValidationError("The uploaded file is not a valid PDF.")

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if not pdf.pages:
                raise FNBPDFValidationError("The PDF contains no pages.")
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise FNBPDFValidationError(
                    f"The PDF exceeds the {MAX_PDF_PAGES}-page processing limit."
                )

            page_texts = [page.extract_text() or "" for page in pdf.pages]
    except FNBPDFValidationError:
        raise
    except Exception as exc:
        error_name = type(exc).__name__.casefold()
        if "password" in error_name or "encrypt" in error_name:
            raise FNBPDFValidationError(
                "The PDF is password-protected. Upload an unprotected FNB statement."
            ) from exc
        raise FNBPDFValidationError(
            "The PDF could not be read. It may be damaged or image-only."
        ) from exc

    statement_text = "\n".join(page_texts)
    date_match = _STATEMENT_DATE.search(statement_text)
    account_match = _ACCOUNT_NUMBER.search(statement_text)
    balance_match = _CURRENT_BALANCE.search(statement_text)

    statement_date = _parse_pdf_date(date_match.group(1)) if date_match else None
    account_digits = re.sub(r"\D", "", account_match.group(1)) if account_match else ""
    account_last_four = account_digits[-4:] if len(account_digits) >= 4 else None
    closing_balance = (
        _signed_amount(balance_match.group(1), balance_match.group(2))
        if balance_match
        else None
    )

    transactions: list[FNBTransaction] = []
    current_row: dict | None = None

    def save_current() -> None:
        if current_row is None:
            return
        description = " ".join(current_row["description"]).strip()
        if not description:
            raise FNBPDFValidationError("A PDF transaction is missing its description.")
        transactions.append(
            FNBTransaction(
                effective_date=current_row["date"],
                description=description,
                reference=None,
                service_fee=current_row["service_fee"],
                amount=current_row["amount"],
                balance=current_row["balance"],
            )
        )
        if len(transactions) > MAX_TRANSACTIONS:
            raise FNBPDFValidationError(
                f"The PDF contains more than {MAX_TRANSACTIONS:,} transactions."
            )

    for page_text in page_texts:
        for raw_line in page_text.splitlines():
            line = " ".join(raw_line.split())
            match = _TRANSACTION_ROW.match(line)
            if match:
                save_current()
                try:
                    service_fee = _parse_decimal(match.group("service_fee"))
                except FNBCSVValidationError as exc:
                    raise FNBPDFValidationError(str(exc)) from exc
                current_row = {
                    "date": _parse_pdf_date(match.group("date")),
                    "description": [match.group("description").strip()],
                    "service_fee": abs(service_fee) if service_fee is not None else None,
                    "amount": _signed_amount(
                        match.group("amount"), match.group("amount_direction")
                    ),
                    "balance": _signed_amount(
                        match.group("balance"), match.group("balance_direction")
                    ),
                }
                continue

            if _DATE_PREFIX.match(line):
                raise FNBPDFValidationError(
                    "A transaction row in this PDF uses an unsupported FNB layout."
                )
            if current_row is not None and not _ignored_line(line):
                current_row["description"].append(line)

    save_current()
    if not transactions:
        raise FNBPDFValidationError(
            "No FNB transactions could be extracted. The PDF may be image-only or use "
            "an unsupported statement layout. The PDF was not saved."
        )

    return FNBStatement(
        statement_date=statement_date,
        account_last_four=account_last_four,
        opening_balance=None,
        closing_balance=closing_balance,
        transactions=transactions,
    )
