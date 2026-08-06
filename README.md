# MYP Academic Assistant Chatbot

A Streamlit chatbot for Grade 9 MYP students, built for a math class project. It answers
questions about homework deadlines, assessment dates, assignment instructions, and concepts
across the student's MYP4 subjects (English, Arabic, French, Individuals and Societies,
Geography, Biology, Chemistry, Physics, Math, and Digital Design — see
`config.settings.SUPPORTED_SUBJECTS`), so students stop missing information scattered across
ManageBac/Teams and stop re-asking the teacher the same questions in class. Students can also
attach a photo or file of a worksheet to a question, and teachers can upload course material in
several formats (see "Teacher tools" below).

Built with [pydantic-ai](https://ai.pydantic.dev/) (an orchestrator agent routing to
logistics/concept/escalation specialist agents) on the Anthropic API with prompt caching
enabled, SQLite for storage, and console logging for observability. See
[ARCHITECTURE.md](ARCHITECTURE.md) for how it fits together.

## Setup

This project uses [uv](https://github.com/astral-sh/uv) to manage the Python version, virtual
environment, and dependencies.

1. Install uv (Windows): `winget install --id=astral-sh.uv -e`
2. Install the project's Python version and dependencies: `uv sync`
3. Set up secrets:
   - Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
   - By default the app uses Anthropic, so set `ANTHROPIC_API_KEY` to a real key. Prompt
     caching (system instructions + tool definitions, 1h TTL) is enabled automatically for
     this provider — see [ARCHITECTURE.md](ARCHITECTURE.md).
   - No Anthropic key yet? Set `LLM_PROVIDER = "huggingface"` and `HF_TOKEN` instead (create a
     free token at https://huggingface.co/settings/tokens) to run on a small free model — no
     other code changes needed, but no prompt caching on that path.
   - `LOG_LEVEL` is optional (defaults to `INFO`); it controls how much routing/tool diagnostic
     detail gets printed to the terminal while the app runs.
4. Run the app: `uv run streamlit run src/app.py`

No manual venv activation is required — `uv run` uses `.venv` automatically.

On first run, `data/app.db` (SQLite, gitignored) is created and seeded from the placeholder
homework/assessment/course-content data in `src/data/seed/`.

## Running the test suite

```
uv run pytest
```

Tests mirror `src/` 1:1 under `tests/`. Deterministic logic (date-range lookups, guardrail
rules, memory/repeated-question detection, content ranking) is tested directly with no LLM
call involved. Agent-level tests use pydantic-ai's `TestModel`/`FunctionModel` to verify
routing and fallback behavior without hitting the network.

## Teacher tools

The sidebar has one panel:

- **Upload course material** — a stand-in for a live ManageBac/Teams integration: drop in a
  file, pick a subject/topic, and it's parsed into the course-content the concept agent draws
  on. Accepts `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`, and (on the Anthropic provider only)
  photos of worksheets/whiteboards/textbook pages, transcribed via Claude vision
  (`agents/vision_agent.py`).

## Frequently asked prompts

Above the chat input, the app shows up to five one-click buttons for the questions asked most
often across students, so a student can send a repeat question without retyping it. It's
empty until questions have been logged — nothing shows on a fresh database.

## Status window

While a question is being answered, the assistant's reply is preceded by a collapsible status
widget showing live progress. Once the answer lands, that trace is preserved as a collapsible
"How I got this answer" expander under the assistant's chat bubble (collapsed by default) —
expanding it shows which route the question was sent to and every tool the specialist agent
actually called that turn (e.g. `get_upcoming_deadlines(subject='math')`), plus which underlying
skill module backs each tool. This persists for every past turn in the conversation, not just the
most recent one.

After the first exchange, the chat input's placeholder text switches from "Ask a question..." to
"Ask a follow-up question..." as a hint that the conversation has context from your last message.

## Student attachments

The chat input also accepts an attached photo or file (same formats as the teacher upload).
Images are shown to the model directly (vision, Anthropic only); other documents are
text-extracted and included as context for that question. Attachments aren't saved as
permanent course content — they only apply to that one question.
