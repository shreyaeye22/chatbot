"""Console logging setup for agent/tool diagnostics.

Configures the root logger with a single stream handler so `uv run streamlit
run src/app.py` prints routing decisions, agent errors, and tool activity to
the terminal. Idempotent - safe to call on every Streamlit rerun.
"""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_configured = False


def setup_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root = logging.getLogger()
    root.setLevel(level.upper())
    root.addHandler(handler)

    _configured = True
