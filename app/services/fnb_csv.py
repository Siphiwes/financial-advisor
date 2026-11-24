"""Parser for the FNB South Africa transaction-history CSV export.

Files are parsed in memory. This module does not persist statements or transactions.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MAX_CSV_BYTES = 20 * 1024 * 1024
MAX_TRANSACTIONS = 10_000


class FNBCSVValidationError(ValueError):
    """Raised when a CSV file does not match the supported FNB transaction layout."""


@dataclass(frozen=True)
class FNBTransaction:
    """A normalized FNB transaction row for preview only."""

    effective_date: date
    description: str
    reference: str | None
    service_fee: Decimal | None
    amount: Decimal
    balance: Decimal | None


@dataclass(frozen=True)
class FNBStatement:
    """Statement metadata and parsed rows, held only for the current request."""

    statement_date: date | None
    account_last_four: str | None
    opening_balance: Decimal | None
    closing_balance: Decimal | None
    transactions: list[FNBTransaction]


_HEADER_ALIASES = {
    "effectivedate": "effective_date",
    "transactiondate": "effective_date",
    "valuedate": "effective_date",
    "description": "description",
    "transactiondescription": "description",
    "narrative": "description",
    "reference": "reference",
    "transactionreference": "reference",
    "chequeref": "reference",
    "chequereference": "reference",
    "chequenumber": "reference",
    "servicefee": "service_fee",
    "debitcreditindicator": "service_fee_indicator",
    "servicefeeindicator": "service_fee_indicator",
    "feeindicator": "service_fee_indicator",
    "amount": "amount",
    "transactionamount": "amount",
    "balance": "balance",
    "calculatedbalance": "balance",
}


def _normalise_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _parse_date(value: str) -> date:
    cleaned = value.strip()
    formats = (
        "%Y%m%d",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
    )
    for date_format in formats:
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise FNBCSVValidationError("A transaction row contains an unsupported date.") from exc


def _parse_decimal(value: str, *, required: bool = False) -> Decimal | None:
    cleaned = value.replace("\u00a0", " ").strip()
    if not cleaned:
        if required:
            raise FNBCSVValidationError("A transaction row is missing its amount.")
        return None

    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1].strip()
    if cleaned.startswith("-") or cleaned.endswith("-"):
        negative = True
        cleaned = cleaned.strip("-").strip()

    cleaned = re.sub(r"^(?:ZAR|R)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" ", "").replace("'", "")

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        decimal_part = cleaned.rsplit(",", 1)[1]
        if len(decimal_part) in (1, 2):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise FNBCSVValidationError("A transaction row contains an invalid amount.") from exc

    if not amount.is_finite():
        raise FNBCSVValidationError("A transaction row contains an invalid amount.")
    return -abs(amount) if negative else amount


def _signed_service_fee(value: str, indicator: str | None) -> Decimal | None:
    fee = _parse_decimal(value)
    if fee is None or not indicator:
        return fee

    direction = indicator.strip().casefold()
    if direction in {"-", "d", "dr", "debit"}:
        return -abs(fee)
    if direction in {"+", "c", "cr", "credit"}:
        return abs(fee)
    return fee


def _find_transaction_header(
    rows: list[list[str]],
) -> tuple[int, dict[str, int]]:
    for row_index, row in enumerate(rows):
        columns: dict[str, int] = {}
        for column_index, label in enumerate(row):
            field = _HEADER_ALIASES.get(_normalise_label(label))
            if field and field not in columns:
                columns[field] = column_index

        if {"effective_date", "description", "amount"}.issubset(columns):
            fee_index = columns.get("service_fee")
            amount_index = columns["amount"]
            if fee_index is not None and amount_index > fee_index:
                for blank_index in range(fee_index + 1, amount_index):
                    if not row[blank_index].strip():
                        columns.setdefault("service_fee_indicator", blank_index)
                        break
            return row_index, columns

    raise FNBCSVValidationError(
        "The CSV does not contain the FNB transaction columns "
        "Effective Date, Description and Amount."
    )


def _metadata_value(rows: list[list[str]], labels: set[str]) -> str | None:
    for row in rows:
        if len(row) < 2:
            continue
        if _normalise_label(row[0]) in labels and row[1].strip():
            return row[1].strip()
    return None


def parse_fnb_csv(content: bytes) -> FNBStatement:
    """Parse a supported FNB CSV export without writing the data to storage."""
    if not content:
        raise FNBCSVValidationError("The uploaded CSV file is empty.")
    if len(content) > MAX_CSV_BYTES:
        raise FNBCSVValidationError("The uploaded CSV file exceeds the 20 MB limit.")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise FNBCSVValidationError("The CSV file encoding is not supported.") from exc

    if "\x00" in text:
        raise FNBCSVValidationError("The uploaded file is not a valid CSV text file.")

    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as exc:
        raise FNBCSVValidationError("The CSV file contains invalid formatting.") from exc

    if not rows:
        raise FNBCSVValidationError("The uploaded CSV file is empty.")

    header_index, columns = _find_transaction_header(rows)
    account_number = _metadata_value(rows[:header_index], {"accountnumber"})
    account_digits = re.sub(r"\D", "", account_number or "")
    account_last_four = account_digits[-4:] if len(account_digits) >= 4 else None

    statement_date_value = _metadata_value(rows[:header_index], {"date", "statementdate"})
    opening_balance_value = _metadata_value(rows[:header_index], {"openingbalance"})
    closing_balance_value = _metadata_value(rows[:header_index], {"closingbalance"})

    statement_date = _parse_date(statement_date_value) if statement_date_value else None
    opening_balance = _parse_decimal(opening_balance_value or "")
    closing_balance = _parse_decimal(closing_balance_value or "")

    transactions: list[FNBTransaction] = []
    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not row or not any(cell.strip() for cell in row):
            continue

        def value_for(field: str, current_row: list[str] = row) -> str:
            index = columns.get(field)
            return (
                current_row[index].strip()
                if index is not None and index < len(current_row)
                else ""
            )

        try:
            effective_date = _parse_date(value_for("effective_date"))
            amount = _parse_decimal(value_for("amount"), required=True)
            if amount is None:
                raise FNBCSVValidationError("A transaction row is missing its amount.")

            transactions.append(
                FNBTransaction(
                    effective_date=effective_date,
                    description=value_for("description"),
                    reference=value_for("reference") or None,
                    service_fee=_signed_service_fee(
                        value_for("service_fee"),
                        value_for("service_fee_indicator") or None,
                    ),
                    amount=amount,
                    balance=_parse_decimal(value_for("balance")),
                )
            )
        except FNBCSVValidationError as exc:
            raise FNBCSVValidationError(
                f"FNB CSV row {row_number} could not be read: {exc}"
            ) from exc

        if len(transactions) > MAX_TRANSACTIONS:
            raise FNBCSVValidationError(
                f"The CSV contains more than {MAX_TRANSACTIONS:,} transactions."
            )

    if not transactions:
        raise FNBCSVValidationError(
            "The FNB CSV contains the expected columns but no transaction rows."
        )

    return FNBStatement(
        statement_date=statement_date,
        account_last_four=account_last_four,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        transactions=transactions,
    )
