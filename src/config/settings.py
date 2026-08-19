"""App configuration: provider selection, secrets/env loading, model factory.

Secrets are read from Streamlit's ``st.secrets`` when available (i.e. when a
``.streamlit/secrets.toml`` exists), falling back to environment variables so
the same code works in tests and in scripts run outside Streamlit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "app.db"
SEED_DIR = REPO_ROOT / "src" / "data" / "seed"
VECTOR_INDEX_PATH = REPO_ROOT / "data" / "vector_index"

DEFAULT_HF_MODEL = "meta-llama/Llama-3.2-3B-Instruct"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEMO_STUDENT_ID = "demo_student"

# The MYP4 subjects this assistant covers, by subject topic rather than course/class
# name (e.g. "SCI-BIO (MYP 4) DG" -> "biology"). Single source of truth: referenced by
# the seed data, the guardrails' on-topic keywords, agent system prompts, tool
# docstrings, and the teacher upload subject picker, so they can't drift apart.
SUPPORTED_SUBJECTS: list[str] = [
    "english",
    "arabic",
    "french",
    "individuals and societies",
    "geography",
    "biology",
    "chemistry",
    "physics",
    "math",
    "digital design",
]


def format_subject_list(subjects: list[str] = SUPPORTED_SUBJECTS) -> str:
    """"a, b, and c" — used to spell out the subject list in agent system prompts."""
    if len(subjects) == 1:
        return subjects[0]
    return ", ".join(subjects[:-1]) + f", and {subjects[-1]}"


def _get_secret(key: str, default: str | None = None) -> str | None:
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        # No secrets.toml, not running under Streamlit, or key not set.
        pass
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    hf_token: str | None
    hf_model_name: str
    anthropic_api_key: str | None
    anthropic_model_name: str
    log_level: str


def load_settings() -> Settings:
    return Settings(
        llm_provider=(_get_secret("LLM_PROVIDER", "anthropic") or "anthropic").lower(),
        hf_token=_get_secret("HF_TOKEN"),
        hf_model_name=_get_secret("HF_MODEL_NAME", DEFAULT_HF_MODEL) or DEFAULT_HF_MODEL,
        anthropic_api_key=_get_secret("ANTHROPIC_API_KEY"),
        anthropic_model_name=_get_secret("ANTHROPIC_MODEL_NAME", DEFAULT_ANTHROPIC_MODEL)
        or DEFAULT_ANTHROPIC_MODEL,
        log_level=(_get_secret("LOG_LEVEL", "INFO") or "INFO").upper(),
    )


def with_api_key_override(settings: Settings, api_key: str | None) -> Settings:
    """Return `settings` with the active provider's key replaced by `api_key`.

    Always replaces - even with None/empty - rather than falling back to the
    app's configured secret when `api_key` is falsy. Students must paste
    their own key into the sidebar (ui.components.render_api_key_sidebar) to
    use the chatbot; the app's built-in ANTHROPIC_API_KEY/HF_TOKEN secrets are
    never used to serve model calls. Callers (app.py) must gate any
    LLM-calling action on the user having supplied a key, since the resulting
    Settings can carry a None key.
    """
    if settings.llm_provider == "anthropic":
        return replace(settings, anthropic_api_key=api_key or None)
    if settings.llm_provider == "huggingface":
        return replace(settings, hf_token=api_key or None)
    return settings


def get_model(settings: Settings | None = None):
    """Build the pydantic-ai Model for the configured provider.

    Kept as a factory (rather than a module-level singleton) so tests can
    swap in a TestModel/FunctionModel without touching this module, and so
    switching providers is a config change, not a code change.
    """
    settings = settings or load_settings()

    if settings.llm_provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(
            settings.anthropic_model_name,
            provider=AnthropicProvider(api_key=settings.anthropic_api_key),
        )

    if settings.llm_provider == "huggingface":
        from pydantic_ai.models.huggingface import HuggingFaceModel
        from pydantic_ai.providers.huggingface import HuggingFaceProvider

        return HuggingFaceModel(
            settings.hf_model_name,
            provider=HuggingFaceProvider(api_key=settings.hf_token),
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER={settings.llm_provider!r}; expected 'huggingface' or 'anthropic'"
    )


def get_model_settings(settings: Settings | None = None):
    """Model-specific settings for the configured provider — currently just
    Anthropic prompt caching.

    Each agent's system prompt and tool list are static per run, which is
    exactly what Anthropic's cache_control breakpoints are for: caching the
    system instructions and tool definitions means only the new user/assistant
    turns are billed as fresh input tokens on each message, instead of
    re-paying for the same system prompt every turn. TTL is '1h' rather than
    the 5m default since a student's questions during a class period can be
    spaced out by more than 5 minutes.

    Returns None for the Hugging Face provider, which has no equivalent
    concept in pydantic-ai.
    """
    settings = settings or load_settings()

    if settings.llm_provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModelSettings

        return AnthropicModelSettings(
            anthropic_cache_instructions="1h",
            anthropic_cache_tool_definitions="1h",
        )

    return None
