"""Compatibility entry point for the container command.

The application is defined in app.main. Keeping this module at the repository
root preserves the existing Uvicorn command used by IBM Code Engine.
"""

from app.main import app

__all__ = ["app"]
