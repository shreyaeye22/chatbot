"""Task: pull the actionable points out of a ManageBac/Teams-style instruction blob.

Deterministic and LLM-free, so the logistics agent can ground its paraphrase
in a concrete, testable extraction rather than relying entirely on the
(possibly small/unreliable) model to not drop a requirement.
"""

from __future__ import annotations

import re

ACTION_VERBS = (
    "submit",
    "complete",
    "bring",
    "write",
    "read",
    "solve",
    "answer",
    "label",
    "draw",
    "show",
    "balance",
    "round",
    "include",
    "upload",
    "finish",
    "prepare",
)


def extract_key_instruction_points(raw_text: str) -> list[str]:
    """Split into sentences and keep the ones that look like an actionable instruction.

    Falls back to returning every non-empty sentence if none contain a
    recognized action verb, so short/unusually-phrased instructions still
    produce something.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_text.strip()) if s.strip()]

    actionable = [
        sentence
        for sentence in sentences
        if any(re.search(rf"\b{verb}\b", sentence.lower()) for verb in ACTION_VERBS)
    ]
    return actionable or sentences
