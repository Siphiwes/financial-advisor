"""User financial-data export and deletion response models."""

from datetime import datetime

from pydantic import BaseModel, Field


class PrivacyExportResponse(BaseModel):
    exported_at: datetime
    user_id: str
    email: str
    data: dict[str, list[dict]]
    record_counts: dict[str, int]
    original_statement_files_included: bool = False


class PrivacyDeleteResponse(BaseModel):
    deleted: bool
    deleted_record_counts: dict[str, int]
    account_access_revoked: bool
    message: str
