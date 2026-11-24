"""FastAPI application factory and current API endpoints."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    application = FastAPI(
        title="Financial Advisor API",
        description="Backend API for the AI Personal Finance Advisor",
        version="0.1.0",
    )

    @application.get("/", tags=["system"])
    def read_root() -> dict[str, str]:
        return {
            "application": "Financial Advisor API",
            "status": "running",
            "version": "0.1.0",
        }

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        # Liveness only. External dependency checks will be separate.
        return {"status": "healthy"}

    return application


app = create_app()
