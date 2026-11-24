"""Environment configuration helpers."""

import os


def get_setting(name: str, default: str | None = None) -> str | None:
    """Return an environment setting without logging its value."""
    return os.getenv(name, default)
