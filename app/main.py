"""FastAPI application factory and API endpoints."""

import logging
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.advisor import router as advisor_router
from app.api.routes.auth import router as auth_router
from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.finance import router as finance_router
from app.api.routes.imports import router as imports_router
from app.api.routes.privacy import router as privacy_router
from app.services.diagnostics import write_diagnostic_event
from app.services.finance import FinanceAuditError

# Loads a local .env file when present. Code Engine supplies deployed values
# through environment variables and does not need a .env file in the image.
load_dotenv()
STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    application = FastAPI(
        title="Financial Advisor API",
        description="Backend API for the AI Personal Finance Advisor",
        version="0.1.0",
    )

    application.include_router(diagnostics_router)
    application.include_router(auth_router)
    application.include_router(imports_router)
    application.include_router(finance_router)
    application.include_router(advisor_router)
    application.include_router(privacy_router)

    @application.middleware("http")
    async def attach_request_id(request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.exception_handler(Exception)
    async def unhandled_exception(request, exc):
        diagnostic_id = getattr(request.state, "request_id", uuid4().hex)
        logger.exception(
            "Unhandled request failure diagnostic_id=%s method=%s path=%s",
            diagnostic_id,
            request.method,
            request.url.path,
        )
        write_diagnostic_event(
            diagnostic_id=diagnostic_id,
            user_id=getattr(request.state, "user_id", None),
            method=request.method,
            path=request.url.path,
            status_code=500,
            exception=exc,
        )
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": diagnostic_id},
            content={
                "detail": (
                    f"Problem found on Server connection. Issue caused by API "
                    f"{request.method} {request.url.path}. "
                    "The server could not complete this operation."
                ),
                "error": {
                    "category": "server_error",
                    "module": "Server connection",
                    "endpoint": request.url.path,
                    "method": request.method,
                    "diagnostic_id": diagnostic_id,
                    "status_code": 500,
                },
            },
        )

    @application.exception_handler(FinanceAuditError)
    async def required_audit_failed(_request, _exc):
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "The request was blocked because a required privacy audit "
                    "event could not be recorded."
                )
            },
        )
    application.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

    @application.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.url.path.startswith(("/api/", "/auth/", "/imports")):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "style-src-attr 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    @application.get("/app", tags=["web"])
    def web_application() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.get("/", tags=["system"])
    def read_root() -> dict[str, str]:
        return {
            "application": "Financial Advisor API",
            "status": "running",
            "version": "0.1.0",
        }

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        # Liveness only. External dependency checks are separate and protected.
        return {"status": "healthy"}

    return application


app = create_app()
