"""Rule-based checks run before a message reaches an agent.

Deliberately not LLM-based: these need to run deterministically (and for
free) on every message, including the off-topic case where we specifically
want to *avoid* spending an LLM call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config.settings import SUPPORTED_SUBJECTS

# Synonyms/sub-topics a student is likely to say instead of the bare subject name
# (e.g. "newton's laws" rather than the word "physics"), grouped by the subject
# they genuinely belong to - so a match actually ties the message to that subject
# (a geography question matches the geography bucket, a history question matches
# the individuals-and-societies bucket, and so on) rather than to an undifferentiated
# blob of keywords from every subject at once.
SUBJECT_KEYWORDS: dict[str, set[str]] = {
    "math": {"maths", "mathematics", "algebra", "geometry", "equation", "linear", "pythagorean"},
    "physics": {"force", "motion", "velocity", "acceleration", "newton", "gravity", "energy"},
    "chemistry": {"chemical", "atom", "atomic", "element", "reaction", "molecule", "bohr"},
    "biology": {"cell", "photosynthesis", "organism", "dna"},
    "english": {"grammar", "essay", "vocabulary", "literature", "novel", "poem", "paragraph"},
    "french": {"comparatif", "superlatif", "conjugaison"},
    "arabic": {"conjugation"},
    "geography": {"map", "climate", "population", "ecosystem"},
    "individuals and societies": {"society", "societies", "civics", "culture", "history"},
    "digital design": {"prototype", "sketch", "design"},
}
# Every subject also matches on its own name (from config.settings.SUPPORTED_SUBJECTS).
for _subject in SUPPORTED_SUBJECTS:
    SUBJECT_KEYWORDS.setdefault(_subject, set()).add(_subject)

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

ON_TOPIC_KEYWORDS = set().union(*SUBJECT_KEYWORDS.values()) | LOGISTICS_KEYWORDS | CONCEPT_QUESTION_KEYWORDS

DIRECT_ANSWER_PATTERNS = [
    re.compile(r"\bjust (tell|give) me the answer\b", re.IGNORECASE),
    re.compile(r"\bwhat('s| is) the answer to\b", re.IGNORECASE),
    re.compile(r"\bsolve (it|this) for me\b", re.IGNORECASE),
    re.compile(r"\bdo (it|this|my homework) for me\b", re.IGNORECASE),
]

# A message that is *only* a greeting (optionally with a short trailing pleasantry,
# e.g. "Hi there") - not a question that happens to open with "hi". Matched on the
# whole message so it doesn't fire on "history..." or other on-topic text that
# merely contains a greeting-like substring.
GREETING_PATTERN = re.compile(
    r"^(hi+|hey+|hello+|howdy|yo|greetings|good\s(morning|afternoon|evening))"
    r"(\s+(there|everyone|guys|class|team))?[\s!.,]*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InputGuardrailResult:
    off_topic: bool
    wants_direct_answer: bool
    is_greeting: bool = False


def check_input(message: str) -> InputGuardrailResult:
    text = message.lower().strip()

    is_greeting = bool(text) and bool(GREETING_PATTERN.match(text))
    on_topic = any(re.search(rf"\b{keyword}\b", text) for keyword in ON_TOPIC_KEYWORDS)
    off_topic = bool(text) and not on_topic and not is_greeting
    wants_direct_answer = any(pattern.search(text) for pattern in DIRECT_ANSWER_PATTERNS)

    return InputGuardrailResult(
        off_topic=off_topic, wants_direct_answer=wants_direct_answer, is_greeting=is_greeting
    )
