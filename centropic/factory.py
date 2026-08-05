"""Application factory — single entry for Gunicorn, workers, and tests."""

from __future__ import annotations

from typing import Any

from flask import Flask


def create_app(config: dict[str, Any] | None = None) -> Flask:
    """Return the Centropic Flask application (layered package entry)."""
    import app as app_module

    flask_app: Flask = app_module.app
    if config:
        flask_app.config.update(config)
    return flask_app
