"""Tests for FNB CSV input validation without invented transaction records."""

import pytest

from app.services.fnb_csv import FNBCSVValidationError, parse_fnb_csv


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
