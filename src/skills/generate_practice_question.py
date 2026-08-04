"""Task (stretch): build a prompt asking the concept agent to generate one
practice question on a topic, deliberately without an answer key attached."""

from __future__ import annotations


def generate_practice_prompt(topic: str) -> str:
    return (
        f"Write one short practice question (no answer key) that tests understanding "
        f"of '{topic}', at a level appropriate for a Grade 9 MYP student."
    )
