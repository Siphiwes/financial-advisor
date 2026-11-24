"""In-memory extraction and validation for text-based FNB PDF statements.

PDF transaction rows are only accepted when the extracted table exposes the same
explicit date, description and amount headers as the supported FNB CSV parser.
No OCR, sign inference, disk writes, or external services are used.
"""

import csv
import io

import pdfplumber

from app.services.fnb_csv import (
    MAX_CSV_BYTES,
    FNBCSVValidationError,
    FNBStatement,
    parse_fnb_csv,
)

MAX_PDF_PAGES = 100


class FNBPDFValidationError(ValueError):
    """Raised when a PDF is unreadable or its transaction layout is unsupported."""


def parse_fnb_pdf(content: bytes) -> FNBStatement:
    """Extract a supported FNB PDF statement entirely in memory."""
    if not content:
        raise FNBPDFValidationError("The uploaded PDF file is empty.")
    if len(content) > MAX_CSV_BYTES:
        raise FNBPDFValidationError("The uploaded PDF file exceeds the 20 MB limit.")
    if not content.startswith(b"%PDF-"):
        raise FNBPDFValidationError("The uploaded file is not a valid PDF.")

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if len(pdf.pages) == 0:
                raise FNBPDFValidationError("The PDF contains no pages.")
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise FNBPDFValidationError(
                    f"The PDF exceeds the {MAX_PDF_PAGES}-page processing limit."
                )
            extracted_tables = []
            for page in pdf.pages:
                extracted_tables.extend(page.extract_tables() or [])
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

    for table in extracted_tables:
        rows = [
            ["" if cell is None else str(cell).replace("\n", " ").strip() for cell in row]
            for row in table
            if row and any(cell is not None and str(cell).strip() for cell in row)
        ]
        if not rows:
            continue
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerows(rows)
        try:
            return parse_fnb_csv(buffer.getvalue().encode("utf-8"))
        except FNBCSVValidationError:
            continue

    raise FNBPDFValidationError(
        "No supported FNB transaction table was detected. This PDF may use a layout "
        "that needs to be mapped before transactions can be previewed. The PDF was not saved."
    )
