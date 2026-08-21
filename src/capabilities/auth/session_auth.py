"""Session-only sign-in: a lightweight role gate, not real authentication.

Lives entirely in st.session_state (gone as soon as the browser tab closes) -
there's no password, no account store, and no server-side identity check.
`role` is a self-reported UI choice used only to decide which controls to
show (e.g. teacher-only upload tools), not a verified permission. See
README's "Sign-in" section before citing this as authentication anywhere.

Takes a plain MutableMapping rather than importing streamlit directly, same
pattern as capabilities.memory.session_memory, so this is testable with an
ordinary dict without needing a live Streamlit session.
"""

from __future__ import annotations

from typing import Any, MutableMapping

LOGGED_IN_KEY = "logged_in"
USER_NAME_KEY = "user_name"
USER_ROLE_KEY = "user_role"

ROLE_STUDENT = "student"
ROLE_TEACHER = "teacher"
VALID_ROLES = (ROLE_STUDENT, ROLE_TEACHER)


def init_auth_state(session_state: MutableMapping[str, Any]) -> None:
    session_state.setdefault(LOGGED_IN_KEY, False)
    session_state.setdefault(USER_NAME_KEY, "")
    session_state.setdefault(USER_ROLE_KEY, None)


def is_logged_in(session_state: MutableMapping[str, Any]) -> bool:
    return bool(session_state.get(LOGGED_IN_KEY, False))


def get_user_name(session_state: MutableMapping[str, Any]) -> str:
    return session_state.get(USER_NAME_KEY, "")


def get_user_role(session_state: MutableMapping[str, Any]) -> str | None:
    return session_state.get(USER_ROLE_KEY)


def log_in(session_state: MutableMapping[str, Any], name: str, role: str) -> None:
    """Record a signed-in user for this session. `role` must be 'student' or
    'teacher' - this only stores a self-reported choice, it doesn't check it
    against anything."""
    if role not in VALID_ROLES:
        raise ValueError(f"Unknown role {role!r}; expected one of {VALID_ROLES}")
    session_state[LOGGED_IN_KEY] = True
    session_state[USER_NAME_KEY] = name
    session_state[USER_ROLE_KEY] = role


def log_out(session_state: MutableMapping[str, Any]) -> None:
    """Reset auth state to logged-out defaults, ending the active session.

    Deliberately only touches the auth keys above - chat history and any
    persisted question logs (capabilities.memory.student_memory) are left
    alone, since logging out ends a session, it doesn't erase records.
    """
    session_state[LOGGED_IN_KEY] = False
    session_state[USER_NAME_KEY] = ""
    session_state[USER_ROLE_KEY] = None
