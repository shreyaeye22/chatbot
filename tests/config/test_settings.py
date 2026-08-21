from __future__ import annotations

import pytest
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.huggingface import HuggingFaceModel

from config.settings import (
    SUPPORTED_SUBJECTS,
    Settings,
    format_subject_list,
    get_model,
    get_model_settings,
    with_anthropic_upgrade,
)


def _settings(**overrides) -> Settings:
    base = dict(
        llm_provider="huggingface",
        hf_token="hf_fake",
        hf_model_name="meta-llama/Llama-3.2-3B-Instruct",
        anthropic_api_key=None,
        anthropic_model_name="claude-sonnet-5",
        log_level="INFO",
    )
    base.update(overrides)
    return Settings(**base)


def test_get_model_builds_huggingface_model_when_configured():
    model = get_model(_settings(llm_provider="huggingface"))
    assert isinstance(model, HuggingFaceModel)


def test_get_model_builds_anthropic_model_when_configured():
    model = get_model(_settings(llm_provider="anthropic", anthropic_api_key="sk-ant-fake"))
    assert isinstance(model, AnthropicModel)


def test_get_model_rejects_unknown_provider():
    with pytest.raises(ValueError):
        get_model(_settings(llm_provider="not-a-real-provider"))


def test_get_model_settings_enables_anthropic_prompt_caching():
    settings = get_model_settings(_settings(llm_provider="anthropic", anthropic_api_key="sk-ant-fake"))

    assert settings["anthropic_cache_instructions"] == "1h"
    assert settings["anthropic_cache_tool_definitions"] == "1h"


def test_get_model_settings_is_none_for_huggingface():
    assert get_model_settings(_settings(llm_provider="huggingface")) is None


def test_supported_subjects_has_no_duplicates():
    assert len(SUPPORTED_SUBJECTS) == len(set(SUPPORTED_SUBJECTS))


def test_format_subject_list_uses_oxford_comma_and_final_and():
    assert format_subject_list(["math", "biology"]) == "math, and biology"
    assert format_subject_list(["math", "biology", "geography"]) == "math, biology, and geography"
    assert format_subject_list(["math"]) == "math"


def test_with_anthropic_upgrade_switches_to_anthropic_with_the_supplied_key():
    settings = _settings(llm_provider="huggingface", hf_token="hf_builtin")

    upgraded = with_anthropic_upgrade(settings, "sk-ant-mine")

    assert upgraded.llm_provider == "anthropic"
    assert upgraded.anthropic_api_key == "sk-ant-mine"


def test_with_anthropic_upgrade_stays_on_huggingface_when_no_key_given():
    settings = _settings(llm_provider="huggingface", hf_token="hf_builtin")

    assert with_anthropic_upgrade(settings, None).llm_provider == "huggingface"
    assert with_anthropic_upgrade(settings, "").llm_provider == "huggingface"
    assert with_anthropic_upgrade(settings, None).hf_token == "hf_builtin"


def test_with_anthropic_upgrade_ignores_a_built_in_anthropic_key_when_no_user_key_given():
    """A deployment's own ANTHROPIC_API_KEY secret must never be used to serve model
    calls - only a student's own pasted key can switch the session to Claude."""
    settings = _settings(llm_provider="anthropic", anthropic_api_key="sk-ant-builtin")

    downgraded = with_anthropic_upgrade(settings, None)

    assert downgraded.llm_provider == "huggingface"
    assert downgraded.anthropic_api_key is None
