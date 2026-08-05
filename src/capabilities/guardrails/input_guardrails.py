"""Rule-based checks run before a message reaches an agent.

Deliberately not LLM-based: these need to run deterministically (and for
free) on every message, including the off-topic case where we specifically
want to *avoid* spending an LLM call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config.settings import SUPPORTED_SUBJECTS

# The subject names themselves (from config.settings.SUPPORTED_SUBJECTS), plus
# synonyms/sub-topics a student is likely to say instead of the bare subject name
# (e.g. "newton's laws" rather than the word "physics").
SUBJECT_KEYWORDS = set(SUPPORTED_SUBJECTS) | {
    "maths",
    "mathematics",
    "algebra",
    "geometry",
    "equation",
    "linear",
    "pythagorean",
    "force",
    "motion",
    "velocity",
    "acceleration",
    "newton",
    "gravity",
    "energy",
    "chemical",
    "atom",
    "atomic",
    "element",
    "reaction",
    "molecule",
    "bohr",
    "cell",
    "photosynthesis",
    "organism",
    "dna",
    "grammar",
    "essay",
    "vocabulary",
    "literature",
    "novel",
    "poem",
    "paragraph",
    "comparatif",
    "superlatif",
    "conjugaison",
    "map",
    "climate",
    "population",
    "ecosystem",
    "society",
    "societies",
    "civics",
    "culture",
    "history",
    "prototype",
    "sketch",
    "design",
}

LOGISTICS_KEYWORDS = {
    "homework",
    "assignment",
    "due",
    "deadline",
    "test",
    "quiz",
    "exam",
    "assessment",
    "class",
    "teacher",
    "instructions",
    "submit",
    "managebac",
    "teams",
}

CONCEPT_QUESTION_KEYWORDS = {
    "explain",
    "understand",
    "concept",
}

ON_TOPIC_KEYWORDS = SUBJECT_KEYWORDS | LOGISTICS_KEYWORDS | CONCEPT_QUESTION_KEYWORDS

DIRECT_ANSWER_PATTERNS = [
    re.compile(r"\bjust (tell|give) me the answer\b", re.IGNORECASE),
    re.compile(r"\bwhat('s| is) the answer to\b", re.IGNORECASE),
    re.compile(r"\bsolve (it|this) for me\b", re.IGNORECASE),
    re.compile(r"\bdo (it|this|my homework) for me\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class InputGuardrailResult:
    off_topic: bool
    wants_direct_answer: bool


def check_input(message: str) -> InputGuardrailResult:
    text = message.lower().strip()

    on_topic = any(re.search(rf"\b{keyword}\b", text) for keyword in ON_TOPIC_KEYWORDS)
    off_topic = bool(text) and not on_topic
    wants_direct_answer = any(pattern.search(text) for pattern in DIRECT_ANSWER_PATTERNS)

    return InputGuardrailResult(off_topic=off_topic, wants_direct_answer=wants_direct_answer)
