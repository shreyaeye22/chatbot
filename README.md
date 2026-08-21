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
logistics/concept/escalation specialist agents), SQLite for storage, and console logging for
observability. The app always starts on a free Hugging Face model — no key needed from
students — with an optional sidebar upgrade to the Anthropic API (with prompt caching enabled)
for a student who pastes in their own Claude key. See [ARCHITECTURE.md](ARCHITECTURE.md) for
how it fits together.

## Setup

This project uses [uv](https://github.com/astral-sh/uv) to manage the Python version, virtual
environment, and dependencies.

1. Install uv (Windows): `winget install --id=astral-sh.uv -e`
2. Install the project's Python version and dependencies: `uv sync`
3. Set up secrets:
   - Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
   - The app always starts on Hugging Face — this is the only model it ever boots with,
     regardless of `LLM_PROVIDER`. Set `HF_TOKEN` to your own Hugging Face token so the free
     model actually works; without it, chat is disabled until a student upgrades to Claude (see
     below). `HF_MODEL_NAME` is optional (defaults to a small free model). No prompt caching on
     this path — see [ARCHITECTURE.md](ARCHITECTURE.md).
   - `ANTHROPIC_API_KEY` in this file is **never** used to serve model calls, even if you set
     `LLM_PROVIDER = "anthropic"` here — Claude is opt-in only, and only a student's own key,
     pasted into the sidebar's "Upgrade to Claude" box (see below), can switch a session to it.
     Leave `ANTHROPIC_API_KEY` as a placeholder; `ANTHROPIC_MODEL_NAME` can still be set to
     control which Claude model a student's key runs against.
   - `LOG_LEVEL` is optional (defaults to `INFO`); it controls how much routing/tool diagnostic
     detail gets printed to the terminal while the app runs.
4. Run the app: `uv run streamlit run src/app.py`

No manual venv activation is required — `uv run` uses `.venv` automatically.

On first run, `data/app.db` (SQLite, gitignored) is created and seeded from the placeholder
homework/assessment/course-content data in `src/data/seed/`. `data/vector_index/` (also
gitignored) is built the same way — a local ChromaDB index over `course_content`, used for
semantic search of class notes (see [ARCHITECTURE.md](ARCHITECTURE.md)). The very first run
also downloads a small (~90MB) local embedding model, cached on disk afterward — this needs
network access once, but no API key and no per-query cost, since embedding runs locally.

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (or GitLab/Bitbucket), then create a new app at
   [share.streamlit.io](https://share.streamlit.io) pointing at it.
2. Set the **main file path** to `src/app.py`.
3. Dependencies are picked up automatically from [requirements.txt](requirements.txt) (a locked
   export of `pyproject.toml`/`uv.lock` via `uv export --no-hashes --no-dev --no-emit-project -o
   requirements.txt` — re-run that after changing dependencies), the Python version from
   [.python-version](.python-version), and the `libgomp1` system package from
   [packages.txt](packages.txt) (needed by `chromadb`'s bundled ONNX runtime on Community Cloud's
   base image).
4. Set secrets in the app's **Settings → Secrets** panel (not committed — `.streamlit/secrets.toml`
   stays gitignored). At minimum set `HF_TOKEN` — the app always starts on Hugging Face, using
   this token, so every visitor can chat with no key of their own. `ANTHROPIC_API_KEY` isn't
   needed here and is ignored for serving chat calls either way — see "Model: Hugging Face by
   default, Claude as an upgrade" below.
5. `data/app.db` and `data/vector_index/` are rebuilt from `src/data/seed/` on every boot (see
   "Setup" above) since Community Cloud's filesystem is ephemeral and resets on every reboot/redeploy
   — including a fresh download of the bundled ONNX embedding model each cold start.

No Procfile/setup.sh needed — those are a Heroku-era pattern; Community Cloud runs the app directly
from the main file path above.

## Running the test suite

```
uv run pytest
```

Tests mirror `src/` 1:1 under `tests/`. Deterministic logic (date-range lookups, guardrail
rules, memory/repeated-question detection) is tested directly with no LLM call involved.
Course-content search (`capabilities/retrieval/vector_store.py`) is tested against a real,
local ChromaDB index too — no LLM call there either, but not instant on a machine's first run
(pays the one-time embedding-model download noted above). Agent-level tests use pydantic-ai's
`TestModel`/`FunctionModel` to verify routing and fallback behavior without hitting the network.

## Sign-in

Before anything else renders, the app shows a sign-in screen: pick a role (**Student** or
**Teacher**) and type a display name, then click **Sign In**. This is a lightweight,
session-based role gate for UX/testing purposes only — **not real authentication**. There's no
password, no account store, and no server-side identity check; `role`/`user_name` are just a
self-reported choice kept in Streamlit's `session_state` for that browser tab
(`capabilities/auth/session_auth.py`), the same way the Anthropic key above is. Signing in as
**Teacher** reveals the "Teacher tools" panel (see below); **Student** shows the standard
chat-only view.

Once signed in, a small circular avatar (the first letter of your name) appears fixed in the
top-right corner of every screen. Clicking it opens a popover with your name, your role, and a
**Log Out** button — used instead of a CSS `:hover` dropdown because `:hover` can't call back
into Streamlit's Python session and a hand-positioned overlay button is fragile across
Streamlit's per-rerun DOM rebuilds; `st.popover` is Streamlit's supported primitive for a
click-to-reveal panel with real widgets in it. Logging out clears `logged_in`, `user_name`, and
`user_role` from `session_state` and returns you to the sign-in screen — it does not clear the
conversation history from that session, since logging out ends a session, it doesn't erase
records.

Since this is a UX/testing role selector rather than real authentication, don't rely on it to
keep content private — anyone can sign in as "Teacher" with any name and no password.

## Model: Hugging Face by default, Claude as an upgrade

The sidebar's first panel, **Model**, shows the app running on the free Hugging Face model —
no key needed from the student, since it runs on the deployment's own built-in `HF_TOKEN`
secret (see "Setup" above). If that secret isn't configured, chat is disabled with an
admin-facing error instead of a request for a key, since a student can't fix a missing
deployment secret by pasting one in.

An **"Upgrade to Claude (optional)"** expander lets a student paste their own legitimate
Anthropic API key to switch just their session to Claude for higher-quality answers and photo
transcription (see "Student attachments" below). The app's own `ANTHROPIC_API_KEY` secret, if
any, is never used to serve a chat call — only a student's own pasted key can turn Claude on.
The key lives only in Streamlit's `session_state` for that browser tab — it's never written to
disk, secrets, or logs, and is forgotten as soon as the tab closes or the field is cleared.

## Teacher tools

The sidebar's second panel — only shown when signed in with the **Teacher** role (see
"Sign-in" above; a student-signed-in session never sees it):

- **Upload course material** — a stand-in for a live ManageBac/Teams integration: drop in a
  file, pick a subject/topic, and it's parsed into the course-content the concept agent draws
  on. Accepts `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`, and (once upgraded to Claude in the
  sidebar) photos of worksheets/whiteboards/textbook pages, transcribed via Claude vision
  (`agents/vision_agent.py`).

## Frequently asked prompts

Pinned near the top of the chat column, above the conversation history, the app shows up to
five one-click buttons for the questions asked most often across students, so a student can
send a repeat question without retyping it — and without having to scroll down past a growing
conversation to find it. It's empty until questions have been logged — nothing shows on a
fresh database.

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
Images are shown to the model directly (vision, Claude only — see "Model" above); other
documents are text-extracted and included as context for that question. Attachments aren't
saved as permanent course content — they only apply to that one question.

## Course files library

To the right of the chat, a panel lists every piece of course content (teacher uploads and
seed data alike) as a table of File / Subject / Owner — "Owner" is currently always "Teacher"
since course content can only be added through the Teacher tools upload panel above, regardless
of which name signed in to upload it (there's no per-user content ownership, just the one
role-gated upload path). Clicking a row scopes the conversation to
just that file's content, shown as an "Attached: ..." badge above the chat input, and stays
attached across follow-up questions until you click Clear. With nothing selected (the default),
questions still search across all course content as usual (semantic search, see
[ARCHITECTURE.md](ARCHITECTURE.md)).
