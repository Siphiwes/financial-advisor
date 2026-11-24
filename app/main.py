"""FastAPI application factory and API endpoints."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
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
STATIC_DIR = Path(__file__).parent / "static"


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
    application.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

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
