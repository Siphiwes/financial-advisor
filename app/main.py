"""FastAPI application factory, browser interface and API endpoints."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.advisor import router as advisor_router
from app.api.routes.auth import router as auth_router
from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.finance import router as finance_router
from app.api.routes.imports import router as imports_router

# Loads a local .env file when present. Code Engine supplies deployed values
# through environment variables and does not need a .env file in the image.
load_dotenv()

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    application = FastAPI(
        title="Financial Advisor API",
        description="Personal finance application for South African users",
        version="0.2.0",
    )

    application.mount(
        "/assets",
        StaticFiles(directory=STATIC_DIR),
        name="assets",
    )

    @application.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    application.include_router(diagnostics_router)
    application.include_router(auth_router)
    application.include_router(imports_router)
    application.include_router(finance_router)
    application.include_router(advisor_router)

    @application.get("/", include_in_schema=False)
    def browser_application() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        # Liveness only. External dependency checks are separate and protected.
        return {"status": "healthy"}

    return application


app = create_app()
