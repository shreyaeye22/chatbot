"""Rule-based sanity check on agent responses before they reach the student.

This is a soft check: it flags/logs suspect responses (e.g. a concept
explanation that reads like a bare final answer) for the teacher digest
rather than trying to rewrite LLM output, which is unreliable to do
post-hoc with a rule-based pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REASONING_MARKERS = (
    "because",
    "step",
    "first",
    "then",
    "try",
    "think about",
    "hint",
    "recall",
    "remember",
)

BARE_RESULT_PATTERN = re.compile(r"=\s*-?\d+(\.\d+)?\s*\.?\s*$")


@dataclass(frozen=True)
class OutputGuardrailResult:
    too_direct: bool


def check_concept_output(answer: str) -> OutputGuardrailResult:
    """Flag concept-agent answers that look like a bare final result with no
    explanation or guiding language — a sign the model gave away the answer
    instead of teaching towards it.
    """
    text = answer.strip()
    word_count = len(text.split())
    has_reasoning_language = any(marker in text.lower() for marker in REASONING_MARKERS)
    looks_like_bare_result = bool(BARE_RESULT_PATTERN.search(text))

    too_direct = word_count <= 20 and looks_like_bare_result and not has_reasoning_language
    return OutputGuardrailResult(too_direct=too_direct)
