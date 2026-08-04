from __future__ import annotations

from capabilities.guardrails.output_guardrails import check_concept_output


def test_bare_numeric_result_is_flagged_as_too_direct():
    result = check_concept_output("x = 42")
    assert result.too_direct is True


def test_explanation_with_reasoning_language_is_not_flagged():
    answer = (
        "Think about what happens if you divide both sides by the coefficient. "
        "First isolate x, then check your answer by substituting it back in."
    )
    result = check_concept_output(answer)
    assert result.too_direct is False


def test_long_answer_is_not_flagged_even_without_reasoning_markers():
    answer = " ".join(["word"] * 30) + " = 42"
    result = check_concept_output(answer)
    assert result.too_direct is False
