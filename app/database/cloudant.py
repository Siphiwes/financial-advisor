"""IBM Cloudant client configuration and safe connectivity diagnostics."""

from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibmcloudant.cloudant_v1 import CloudantV1

from app.core.config import get_setting

DEFAULT_DATABASE = "finance-advisor-db"


class CloudantConfigurationError(ValueError):
    """Raised when required Cloudant configuration is missing or invalid."""


class CloudantDiagnosticError(RuntimeError):
    """Raised when a Cloudant diagnostic cannot be verified."""


def get_database_name() -> str:
    """Return the configured database name, defaulting to the provisioned database."""
    database = get_setting("CLOUDANT_DATABASE", DEFAULT_DATABASE)
    if not database or not database.strip():
        raise CloudantConfigurationError("CLOUDANT_DATABASE is not configured.")
    return database.strip()


def get_cloudant_client() -> CloudantV1:
    """Build a Cloudant SDK client using the Code Engine IAM secret references."""
    api_key = get_setting("CLOUDANT_API_KEY")
    service_url = get_setting("CLOUDANT_URL")

    if not api_key or not api_key.strip():
        raise CloudantConfigurationError("CLOUDANT_API_KEY is not configured.")
    if not service_url or not service_url.strip():
        raise CloudantConfigurationError("CLOUDANT_URL is not configured.")

    parsed_url = urlsplit(service_url.strip())
    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise CloudantConfigurationError("CLOUDANT_URL must be a valid HTTPS service URL.")

    client = CloudantV1(IAMAuthenticator(api_key.strip()))
    client.set_service_url(service_url.strip().rstrip("/"))
    return client


def verify_document_round_trip(client: CloudantV1, database: str) -> dict[str, bool]:
    """Create, read, verify and delete a temporary non-financial diagnostic document.

    The probe contains only a random nonce and a timestamp. It is removed after
    successful verification and is never treated as a financial transaction.
    """
    nonce = uuid4().hex
    probe_document = {
        "type": "connection_diagnostic",
        "probe_nonce": nonce,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    created: dict = {}
    document_id: str | None = None

    try:
        created = client.post_document(db=database, document=probe_document).get_result()
        document_id = created.get("id")
        if not document_id or not created.get("rev"):
            raise CloudantDiagnosticError("Cloudant did not confirm document creation.")

        retrieved = client.get_document(db=database, doc_id=document_id).get_result()
        if retrieved.get("probe_nonce") != nonce:
            raise CloudantDiagnosticError("The diagnostic document could not be verified.")

        revision = retrieved.get("_rev")
        if not revision:
            raise CloudantDiagnosticError("Cloudant did not return the document revision.")

        deleted = client.delete_document(
            db=database,
            doc_id=document_id,
            rev=revision,
        ).get_result()
        if deleted.get("ok") is not True:
            raise CloudantDiagnosticError("Cloudant did not confirm diagnostic document deletion.")

        return {"create": True, "read": True, "delete": True}
    except Exception:
        # Best-effort cleanup if creation succeeded but a later check failed.
        if document_id:
            try:
                current = client.get_document(db=database, doc_id=document_id).get_result()
                current_revision = current.get("_rev")
                if current_revision:
                    client.delete_document(
                        db=database,
                        doc_id=document_id,
                        rev=current_revision,
                    ).get_result()
            except Exception:
                pass
        raise
