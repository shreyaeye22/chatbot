from __future__ import annotations

from skills.generate_practice_question import generate_practice_prompt


def test_prompt_names_the_topic_and_excludes_an_answer_key():
    prompt = generate_practice_prompt("photosynthesis")

    assert "photosynthesis" in prompt
    assert "no answer key" in prompt.lower()
