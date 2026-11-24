"""Tests for FNB CSV input validation without invented transaction records."""

import pytest

from app.services.fnb_csv import MAX_CSV_BYTES, FNBCSVValidationError, parse_fnb_csv


def test_rejects_csv_without_fnb_transaction_columns() -> None:
    content = b"Date,Merchant,Debit,Credit\n"

    with pytest.raises(FNBCSVValidationError, match="does not contain the FNB"):
        parse_fnb_csv(content)


def test_rejects_fnb_layout_without_transaction_rows() -> None:
    content = (
        b"Effective Date,Description,Reference,Service Fee,"
        b"Debit / Credit indicator,Amount,Balance\n"
    )

    with pytest.raises(FNBCSVValidationError, match="no transaction rows"):
        parse_fnb_csv(content)


def test_rejects_empty_upload() -> None:
    with pytest.raises(FNBCSVValidationError, match="empty"):
        parse_fnb_csv(b"")


def test_rejects_csv_above_20_mb_upload_limit() -> None:
    content = b"x" * (MAX_CSV_BYTES + 1)

    with pytest.raises(FNBCSVValidationError, match="20 MB limit"):
        parse_fnb_csv(content)


def test_fnb_csv_upload_limit_is_20_mb() -> None:
    assert MAX_CSV_BYTES == 20 * 1024 * 1024


def test_recognizes_fnb_account_transaction_history_date_header() -> None:
    content = b"ACCOUNT TRANSACTION HISTORY\nDate,Amount,Balance,Description\n"

    with pytest.raises(FNBCSVValidationError, match="no transaction rows"):
        parse_fnb_csv(content)
