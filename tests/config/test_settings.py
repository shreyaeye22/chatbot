from __future__ import annotations

import pytest
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.huggingface import HuggingFaceModel

from config.settings import Settings, get_model


def _settings(**overrides) -> Settings:
    base = dict(
        llm_provider="huggingface",
        hf_token="hf_fake",
        hf_model_name="meta-llama/Llama-3.2-3B-Instruct",
        anthropic_api_key=None,
        anthropic_model_name="claude-sonnet-5",
        logfire_token=None,
    )
    base.update(overrides)
    return Settings(**base)


def test_get_model_builds_huggingface_model_by_default():
    model = get_model(_settings(llm_provider="huggingface"))
    assert isinstance(model, HuggingFaceModel)


def test_get_model_builds_anthropic_model_when_configured():
    model = get_model(_settings(llm_provider="anthropic", anthropic_api_key="sk-ant-fake"))
    assert isinstance(model, AnthropicModel)


def test_get_model_rejects_unknown_provider():
    with pytest.raises(ValueError):
        get_model(_settings(llm_provider="not-a-real-provider"))
