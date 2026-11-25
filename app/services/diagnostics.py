"""Persistent, privacy-conscious application diagnostics."""

from __future__ import annotations

import logging
import re
import traceback
from datetime import UTC, datetime
from uuid import uuid4

from app.database.cloudant import get_cloudant_client, get_database_name

logger = logging.getLogger(__name__)
MAX_DIAGNOSTIC_RECORDS = 500
SECRET_PATTERNS = (
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:password|passwd|api[_-]?key|token|secret)\s*[=:]\s*)[^\s,;]+"), r"\1[REDACTED]"),
)


def _redact(value: str) -> str:
    result = value
    for pattern, replacement in SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result[:12000]


def write_diagnostic_event(
    *,
    diagnostic_id: str,
    user_id: str | None,
    method: str,
    path: str,
    status_code: int,
    exception: Exception,
) -> None:
    """Persist a diagnostic without request bodies, headers, or finance payloads."""
    stack = "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )
    document = {
        "type": "application_diagnostic",
        "diagnostic_id": diagnostic_id,
        "user_id": user_id,
        "occurred_at": datetime.now(UTC).isoformat(),
        "method": method,
        "path": path,
        "status_code": status_code,
        "exception_type": type(exception).__name__,
        "message": _redact(str(exception)),
        "stack_trace": _redact(stack),
    }
    try:
        client = get_cloudant_client()
        client.post_document(db=get_database_name(), document=document).get_result()
    except Exception as logging_error:
        # Cloudant may be the failing dependency. Keep a server-log fallback and
        # never let diagnostic persistence replace the original API exception.
        logger.error(
            "Persistent diagnostic write failed id=%s type=%s",
            diagnostic_id,
            type(logging_error).__name__,
        )


def list_diagnostic_events(user_id: str, limit: int = 50) -> list[dict]:
    """Return recent diagnostics for the authenticated user only."""
    client = get_cloudant_client()
    database = get_database_name()
    response = client.post_find(
        db=database,
        selector={"type": "application_diagnostic", "user_id": user_id},
        limit=MAX_DIAGNOSTIC_RECORDS,
    ).get_result()
    documents = response.get("docs", [])
    documents.sort(key=lambda item: item.get("occurred_at", ""), reverse=True)
    return [
        {
            "diagnostic_id": item.get("diagnostic_id"),
            "occurred_at": item.get("occurred_at"),
            "method": item.get("method"),
            "path": item.get("path"),
            "status_code": item.get("status_code"),
            "exception_type": item.get("exception_type"),
            "message": item.get("message"),
            "stack_trace": item.get("stack_trace"),
        }
        for item in documents[: max(1, min(limit, 100))]
    ]
