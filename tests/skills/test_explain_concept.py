from __future__ import annotations

from skills.explain_concept import rank_content, select_best_content

ROWS = [
    {
        "subject": "physics",
        "topic": "newton's laws",
        "content": "Force equals mass times acceleration, F = m * a.",
    },
    {
        "subject": "physics",
        "topic": "speed velocity acceleration",
        "content": "Velocity is displacement over time, including direction.",
    },
]


def test_select_best_content_picks_the_row_matching_the_query():
    best = select_best_content(ROWS, "what is newton's second law about force and mass")

    assert best["topic"] == "newton's laws"


def test_select_best_content_returns_none_when_nothing_matches():
    assert select_best_content(ROWS, "how do plants make their own food") is None


def test_select_best_content_returns_none_for_empty_rows():
    assert select_best_content([], "anything") is None


def test_rank_content_orders_best_match_first_and_drops_zero_overlap():
    ranked = rank_content(ROWS, "velocity direction displacement", top_n=3)

    assert [row["topic"] for row in ranked] == ["speed velocity acceleration"]
