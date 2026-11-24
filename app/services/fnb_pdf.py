"""In-memory extraction and parsing for FNB South Africa PDF statements.

The parser maps the five-column transaction table found in FNB's downloadable
account transaction-history PDF. It never writes the original PDF to disk or
persists extracted data during preview.
"""

import io
import re
from datetime import datetime

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


class FNBPDFValidationError(ValueError):
    """Raised when a PDF is unreadable or its transaction layout is unsupported."""


def _signed_pdf_money(value: str, *, required: bool = False):
    """Parse FNB PDF amounts carrying an explicit DR/CR suffix."""
    cleaned = (value or "").replace("\u00a0", " ").strip()
    if not cleaned:
        if required:
            raise FNBPDFValidationError("A PDF transaction is missing its amount or balance.")
        return None
    match = re.fullmatch(r"(.+?)\s+(DR|CR)", cleaned, flags=re.IGNORECASE)
    if not match:
        raise FNBPDFValidationError(
            "The PDF contains an amount without a recognised DR/CR indicator."
        )
    try:
        amount = _parse_decimal(match.group(1), required=True)
    except FNBCSVValidationError as exc:
        raise FNBPDFValidationError("The PDF contains an invalid monetary value.") from exc
    return -abs(amount) if match.group(2).upper() == "DR" else abs(amount)


def _pdf_metadata(text: str):
    date_match = re.search(
        r"(?im)^\s*Date:\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s*$",
        text,
    )
    account_match = re.search(
        r"(?im)^\s*Selected Account:\s*([0-9 ]+)\s*$",
        text,
    )
    statement_date = (
        datetime.strptime(date_match.group(1), "%d %b %Y").date()
        if date_match
        else None
    )
    account_digits = re.sub(r"\D", "", account_match.group(1)) if account_match else ""
    account_last_four = account_digits[-4:] if len(account_digits) >= 4 else None
    return statement_date, account_last_four


def parse_fnb_pdf(content: bytes) -> FNBStatement:
    """Parse the supported five-column FNB transaction-history PDF in memory."""
    if not content:
        raise FNBPDFValidationError("The uploaded PDF file is empty.")
    if len(content) > MAX_CSV_BYTES:
        raise FNBPDFValidationError("The uploaded PDF file exceeds the 20 MB limit.")
    if not content.startswith(b"%PDF-"):
        raise FNBPDFValidationError("The uploaded file is not a valid PDF.")

    transactions: list[FNBTransaction] = []
    statement_date = None
    account_last_four = None
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if not pdf.pages:
                raise FNBPDFValidationError("The PDF contains no pages.")
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise FNBPDFValidationError(
                    f"The PDF exceeds the {MAX_PDF_PAGES}-page processing limit."
                )
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                parsed_date, parsed_account = _pdf_metadata(page_text)
                statement_date = statement_date or parsed_date
                account_last_four = account_last_four or parsed_account

                for table in page.extract_tables() or []:
                    for row in table:
                        cells = [
                            "" if cell is None else str(cell).replace("\n", " ").strip()
                            for cell in row
                        ]
                        if len(cells) < 5:
                            continue
                        (
                            date_text,
                            description,
                            service_fee_text,
                            amount_text,
                            balance_text,
                        ) = cells[:5]
                        if not re.fullmatch(r"\d{1,2}\s+[A-Za-z]{3}\s+20\d{2}", date_text):
                            # Ignore blank rows and section labels such as "OTHER".
                            continue
                        if not description:
                            raise FNBPDFValidationError(
                                "A PDF transaction is missing its description."
                            )
                        try:
                            effective_date = _parse_date(date_text)
                            amount = _signed_pdf_money(amount_text, required=True)
                            balance = _signed_pdf_money(balance_text, required=True)
                            service_fee = _parse_decimal(service_fee_text)
                        except FNBCSVValidationError as exc:
                            raise FNBPDFValidationError(
                                "A PDF transaction contains an invalid date or monetary value."
                            ) from exc
                        transactions.append(
                            FNBTransaction(
                                effective_date=effective_date,
                                description=re.sub(r"\s+", " ", description).strip(),
                                reference=None,
                                service_fee=service_fee,
                                amount=amount,
                                balance=balance,
                            )
                        )
                        if len(transactions) > MAX_TRANSACTIONS:
                            raise FNBPDFValidationError(
                                f"The PDF contains more than {MAX_TRANSACTIONS:,} transactions."
                            )
    except FNBPDFValidationError:
        raise
    except Exception as exc:
        name = type(exc).__name__.casefold()
        if "password" in name or "encrypt" in name:
            raise FNBPDFValidationError(
                "The PDF is password-protected. Upload an unprotected FNB statement."
            ) from exc
        raise FNBPDFValidationError(
            "The PDF could not be read. It may be damaged or image-only."
        ) from exc

    if not transactions:
        raise FNBPDFValidationError(
            "No supported FNB transaction rows were detected. The PDF was not saved."
        )

    return FNBStatement(
        statement_date=statement_date,
        account_last_four=account_last_four,
        opening_balance=None,
        closing_balance=None,
        transactions=transactions,
    )
