"""Logfire instrumentation for agent/tool call traces.

Works the same regardless of LLM provider (Anthropic or Hugging Face) since
it instruments pydantic-ai's own spans, not a provider-specific API. Runs in
local-only mode when no LOGFIRE_TOKEN is configured, so the app works
without a Logfire account too.
"""

from __future__ import annotations

import logfire

_configured = False


def setup_logfire(token: str | None = None) -> None:
    global _configured
    if _configured:
        return

    logfire.configure(
        token=token,
        send_to_logfire="if-token-present",
        service_name="myp-academic-assistant",
    )
    logfire.instrument_pydantic_ai()
    _configured = True
