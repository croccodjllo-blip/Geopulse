"""Pytest defaults for GeoPulse hardening suite."""

from __future__ import annotations

import os
import tempfile

# Secret obbligatorio se FLASK_DEBUG!=1 al import di app.
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-not-for-prod")
os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("ASYNC_ANALYZE", "0")
os.environ.setdefault("MEASURED_SOV_ON_ANALYZE", "0")
os.environ.setdefault("ALLOW_DROP_ANALYSIS_JOBS", "1")
os.environ.setdefault("CENTROPIC_SKIP_PROD_GUARDS", "1")
os.environ.setdefault("BEHIND_NGINX", "1")

# SQLite file temporaneo ( :memory: non è condiviso tra connessioni SQLAlchemy ).
_tmp = tempfile.NamedTemporaryFile(prefix="geopulse-test-", suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
