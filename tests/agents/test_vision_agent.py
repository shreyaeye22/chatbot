from __future__ import annotations

from pydantic_ai import BinaryContent
from pydantic_ai import messages as m
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agents.vision_agent import vision_agent


def test_vision_agent_transcribes_image_content():
    def _reply(messages: list, info: AgentInfo) -> m.ModelResponse:
        return m.ModelResponse(
            parts=[m.TextPart(content="Transcribed notes: population pyramid diagram.")]
        )

    result = vision_agent.run_sync(
        [BinaryContent(data=b"fake-image-bytes", media_type="image/png")],
        model=FunctionModel(_reply),
    )

    assert result.output == "Transcribed notes: population pyramid diagram."
