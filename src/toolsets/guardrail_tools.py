"""Tools: rule-based off-topic/academic-honesty checks.

Called directly by the orchestration layer (agents/orchestrator.py), not
exposed as LLM-invoked tools — a guardrail that only runs if the model
remembers to call it isn't a guardrail. Thin wrapper over
capabilities/guardrails so the rules stay unit-testable on their own.
"""

from __future__ import annotations

from capabilities.guardrails.input_guardrails import InputGuardrailResult, check_input
from capabilities.guardrails.output_guardrails import OutputGuardrailResult, check_concept_output


def check_input_message(message: str) -> InputGuardrailResult:
    return check_input(message)


def check_concept_answer(answer: str) -> OutputGuardrailResult:
    return check_concept_output(answer)
