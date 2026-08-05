# MYP Academic Assistant Chatbot

A Streamlit chatbot for Grade 9 MYP students, built for a math class project. It answers
questions about homework deadlines, assessment dates, assignment instructions, and concepts
across the student's MYP4 subjects (English, Arabic, French, Individuals and Societies,
Geography, Biology, Chemistry, Physics, Math, and Digital Design — see
`config.settings.SUPPORTED_SUBJECTS`), so students stop missing information scattered across
ManageBac/Teams and stop re-asking the teacher the same questions in class.

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

The sidebar has two panels:

- **Upload a worksheet (.docx)** — a stand-in for a live ManageBac/Teams integration: drop in
  a Word document, pick a subject/topic, and it's parsed into the course-content the concept
  agent draws on.
- **Most common student questions** — a digest of questions asked 2+ times across students,
  so the teacher can see what's worth addressing in class instead of one-on-one.
