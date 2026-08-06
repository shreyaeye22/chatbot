from __future__ import annotations

from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import Status


def test_manual_check():
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)
    assert not at.exception

    chat_input = at.chat_input[0]
    print("PLACEHOLDER BEFORE:", repr(chat_input.placeholder))

    chat_input.set_value("when is my math homework due?")
    at.run(timeout=60)
    assert not at.exception, at.exception

    for status in at.get(Status):
        print("STATUS LABEL:", status.label, "STATE:", status.state)
        for child in status.children.values():
            print("  CHILD:", type(child).__name__, getattr(child, "value", None))

    chat_input2 = at.chat_input[0]
    print("PLACEHOLDER AFTER:", repr(chat_input2.placeholder))
