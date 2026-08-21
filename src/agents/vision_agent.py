"""Transcribes an uploaded image (worksheet, whiteboard, textbook page) into
study-notes text, for the teacher-upload flow (see data/document_ingest.py's
`store_course_content` and app.py's upload handler).

Vision-only, no tools/deps - a single-purpose transcription step. Only usable
on a vision-capable provider (Anthropic); app.py gates image upload on
`vision_enabled` (the effective, post-upgrade settings' `llm_provider ==
"anthropic"` - true only once a student has pasted their own Claude key into
the sidebar, see config.settings.with_anthropic_upgrade).
"""

from __future__ import annotations

from pydantic_ai import Agent

SYSTEM_PROMPT = """
You transcribe an image of a school worksheet, whiteboard, or textbook page into clear,
well-organized study notes in plain text.

Rules:
- Preserve all text and equations exactly as shown.
- Describe any diagrams or figures in words, in place of where they appear.
- Do not solve any problems shown, answer any questions shown, or add information that isn't
  in the image - just faithfully transcribe and organize what's there.
"""

vision_agent = Agent(
    model=None,
    output_type=str,
    system_prompt=SYSTEM_PROMPT,
)
