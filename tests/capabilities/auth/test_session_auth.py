from __future__ import annotations

import pytest

from capabilities.auth.session_auth import (
    get_user_name,
    get_user_role,
    init_auth_state,
    is_logged_in,
    log_in,
    log_out,
)


def test_init_auth_state_defaults_to_logged_out():
    session_state: dict = {}

    init_auth_state(session_state)

    assert is_logged_in(session_state) is False
    assert get_user_name(session_state) == ""
    assert get_user_role(session_state) is None


def test_init_auth_state_does_not_clobber_an_existing_session():
    session_state = {"logged_in": True, "user_name": "Alex", "user_role": "student"}

    init_auth_state(session_state)

    assert is_logged_in(session_state) is True
    assert get_user_name(session_state) == "Alex"
    assert get_user_role(session_state) == "student"


def test_log_in_records_name_and_role():
    session_state: dict = {}
    init_auth_state(session_state)

    log_in(session_state, "Alex", "student")

    assert is_logged_in(session_state) is True
    assert get_user_name(session_state) == "Alex"
    assert get_user_role(session_state) == "student"


def test_log_in_rejects_an_unknown_role():
    session_state: dict = {}
    init_auth_state(session_state)

    with pytest.raises(ValueError):
        log_in(session_state, "Alex", "admin")

    assert is_logged_in(session_state) is False


def test_log_out_resets_to_logged_out_defaults():
    session_state: dict = {}
    init_auth_state(session_state)
    log_in(session_state, "Ms. Smith", "teacher")

    log_out(session_state)

    assert is_logged_in(session_state) is False
    assert get_user_name(session_state) == ""
    assert get_user_role(session_state) is None


def test_log_out_does_not_touch_chat_history():
    session_state = {"chat_history": [{"role": "user", "content": "hi"}]}
    init_auth_state(session_state)
    log_in(session_state, "Alex", "student")

    log_out(session_state)

    assert session_state["chat_history"] == [{"role": "user", "content": "hi"}]
