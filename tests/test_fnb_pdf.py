"""Tests for FNB PDF upload validation without fabricated transaction data."""

import pytest

from app.services.fnb_csv import MAX_CSV_BYTES
from app.services.fnb_pdf import FNBPDFValidationError, parse_fnb_pdf


def test_rejects_empty_pdf() -> None:
    with pytest.raises(FNBPDFValidationError, match="empty"):
        parse_fnb_pdf(b"")


def test_rejects_non_pdf_content() -> None:
    with pytest.raises(FNBPDFValidationError, match="not a valid PDF"):
        parse_fnb_pdf(b"not a pdf")


def test_rejects_pdf_above_20_mb_limit() -> None:
    content = b"%PDF-" + b"x" * MAX_CSV_BYTES
    with pytest.raises(FNBPDFValidationError, match="20 MB limit"):
        parse_fnb_pdf(content)


def test_rejects_pdf_header_without_valid_document() -> None:
    with pytest.raises(FNBPDFValidationError, match="could not be read"):
        parse_fnb_pdf(b"%PDF-1.7\n")
