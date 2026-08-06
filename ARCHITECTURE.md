# Architecture

## Overall flow

```
Streamlit UI (src/app.py)
  -> ui.components.build_message_content()  (text, or [text, image] for an attachment)
  -> agents/orchestrator.route_and_answer()
       -> capabilities/guardrails (input check: off-topic? wants direct answer?
                                    skipped for off-topic when there's an attachment)
       -> agents/orchestrator_agent  (LLM call: pick a route - can see an attached image too)
       -> agents/{logistics,concept,escalation}_agent  (LLM call: answer, using toolsets)
            -> toolsets/*  (thin wrappers)
                 -> skills/*  (deterministic business logic)
                      -> data/db.py (SQLite)
       -> capabilities/guardrails (output check, concept answers only)
       -> capabilities/memory (log the question's text; usage/cost logged via logging)
  <- AgentAnswer(text, route, ...)
Streamlit UI renders the reply (simulated stream) and updates session memory
```

Each turn does at most two LLM calls: one routing call (structured output) and one specialist
call. Off-topic messages short-circuit before any LLM call at all.

## Why the split is this way

**Orchestrator + 3 specialist agents**, rather than one flat agent: `concept_agent` needs a
genuinely different behavioral contract (hint, never hand over the final answer) from
`logistics_agent` (short, factual, date-grounded), and mixing both into one system prompt
dilutes both. `escalation_agent` exists as a dedicated, low-stakes fallback so a confused or
failed routing decision still produces a reasonable, honest response instead of a crash or a
hallucinated answer.

**capabilities/ vs toolsets/ vs skills/:**
- `skills/` holds the actual deterministic logic (date-range filtering, keyword ranking,
  instruction extraction, digest building) — plain functions, fully unit-testable with no
  agent or LLM involved.
- `toolsets/` are thin `@tool`-shaped wrappers (`RunContext[AgentDeps]` in, plain value out)
  that open a short-lived DB connection and delegate to `skills/`/`capabilities/`. This is
  the layer actually bound to an `Agent(tools=[...])`.
- `capabilities/` holds cross-cutting concerns that aren't "one task" (memory, guardrails,
  observability) and are shared by multiple agents/toolsets.

**Guardrails are not LLM tools.** `toolsets/guardrail_tools.py` exists as a thin wrapper for
folder-convention consistency, but `agents/orchestrator.py` calls it directly, not as an
agent-invoked tool — a rule that only fires if the model remembers to call it isn't a
guardrail, especially with a small model.

**Question logging is deterministic**, done by the orchestrator after routing, not via an
agent tool call, for the same reliability reason.

## Model provider (and why it's swappable)

`config/settings.py` builds the pydantic-ai `Model` (and its `model_settings`) from an
`LLM_PROVIDER` setting:

- `anthropic` (default): `AnthropicModel`, requires `ANTHROPIC_API_KEY`. Prompt caching is on
  (see below).
- `huggingface`: `HuggingFaceModel` via HF Inference Providers, a free small model
  (`meta-llama/Llama-3.2-3B-Instruct` by default) — a no-cost fallback for local development
  if you don't have an Anthropic key. No prompt caching support on this path.

Switching is a config change in `.streamlit/secrets.toml`, not a code change.

**Known tradeoff on the Hugging Face path:** small models are less reliable at structured
tool-calling/routing than Claude. Mitigations in `agents/orchestrator.py`: the routing decision
is a minimal structured output (not a multi-step tool chain), and `_run_agent_safely` catches
any exception from a model call (bad output, timeout, rate limit) and falls back to a fixed
escalation reply rather than crashing the chat. These same safeguards apply on the Anthropic
path too, just less likely to trigger.

### Prompt caching (Anthropic only)

`config/settings.get_model_settings()` returns an `AnthropicModelSettings` with
`anthropic_cache_instructions="1h"` and `anthropic_cache_tool_definitions="1h"` whenever
`LLM_PROVIDER=anthropic`. Each specialist agent's system prompt and tool list are static per
run, which is exactly what these cache breakpoints are for: on the second and later turns in a
session, Anthropic serves the system instructions and tool definitions from cache instead of
re-billing them as fresh input tokens on every message. The `1h` TTL (rather than the 5m
default) is deliberate — a student's questions during a class period are often spaced further
apart than 5 minutes, and a 5m cache would frequently miss between questions.

`route_and_answer()` threads `model_settings` through to both the orchestrator's routing call
and whichever specialist agent handles the turn (`agents/orchestrator._run_agent_safely`), so
caching applies uniformly regardless of route. Returns `None` for the Hugging Face provider,
which has no equivalent concept in pydantic-ai — the app still runs, just without caching.

## Observability (console logging)

`capabilities/observability/logging_setup.py` configures Python's standard `logging` module
once at app startup (`setup_logging(settings.log_level)`), attaching a single formatted stream
handler to the root logger. `agents/orchestrator.py` logs at each decision point — off-topic
rejection, the routing outcome, any agent failure/fallback, and output-guardrail flags — so
`uv run streamlit run src/app.py` prints a readable trace of what the assistant did for each
message straight to the terminal. `LOG_LEVEL` (default `INFO`) controls verbosity; this works
identically regardless of which model provider is active.

**Token/cache-token/cost logging:** `agents/orchestrator._log_usage()` logs, after the
routing call, after the specialist call, and as a per-turn total: input tokens, cache-read
tokens, cache-write tokens, output tokens, request count, and an estimated cost. The cost comes
from pydantic-ai's `RunUsage.cost` (computed via [genai-prices](https://github.com/pydantic/genai-prices)
from the model/provider and token counts) rather than a pricing table maintained here, and logs
as "unknown" rather than a wrong number if a model/provider can't be priced. Example line:
`logistics usage: input=2803 (cache_read=2506, cache_write=0) output=126 requests=2 cost=$0.0024`
— the high `cache_read` relative to `input` there is prompt caching (see above) working.

**In-UI tool trace:** `agents/orchestrator._tool_calls()` extracts every `ToolCallPart` from
the specialist agent's `new_messages()` (tool name + args) and attaches it to
`AgentAnswer.tool_calls`. `ui.components.render_tool_trace()` writes that, plus the chosen route,
into the `st.status(...)` widget `app.py` already wraps each turn in — the same collapsible
widget, just with real per-turn content instead of static progress labels. `TOOL_SKILLS` in
`ui/components.py` maps each tool name to the `skills`/`capabilities` module that actually does
the work, purely for that display (the orchestrator itself doesn't need to know skill names).

## Persistence

SQLite (`data/app.db`, gitignored), created and seeded from `src/data/seed/*.json` on first
run (`data/db.py`). Chosen over a hosted DB (costs money, unneeded at this scale) and over
plain JSON/CSV as the primary store (SQLite gives real date-range queries and avoids
read/write races). Connections are opened per-call rather than held as shared state, because
Streamlit reruns the whole script on every interaction.

Tables: `homework`, `assessments`, `course_content`, `question_log` (every question asked,
with its route and whether it was answered — powers the teacher digest via
`capabilities/memory/class_memory.py`).

**Getting real content in:** no live ManageBac/Teams integration. Instead, the sidebar's
"Upload course material" panel (`data/document_ingest.py`) lets a teacher drop in a file, which
is parsed into a `course_content` row for the concept agent to draw on.

## Documents and images

Two separate paths, deliberately not unified, since only one of them needs an LLM call:

- **Text documents** (`.docx`, `.pdf`, `.pptx`, `.txt`, `.md`) — `data/document_ingest.py`
  extracts text deterministically (`python-docx`, `pypdf`, `python-pptx`, or a plain read) and
  either stores it directly as `course_content` (teacher upload) or folds it into the chat
  prompt as `"[Attached file '<name>':]\n<text>"` (student attachment,
  `ui.components.build_message_content`). No LLM call needed, so it works on either provider.
- **Images** (worksheets, whiteboards, textbook photos) — need an LLM to actually read, so they
  go through `agents/vision_agent.py` (teacher upload: transcribed once into `course_content`)
  or are passed straight through as multimodal content to whichever agent handles that chat
  turn (student attachment) via pydantic-ai's `BinaryContent`. Either way this requires a
  vision-capable model, so both upload paths in `app.py` check
  `load_settings().llm_provider == "anthropic"` and hide/disable the image option otherwise —
  there's no image support on the Hugging Face fallback.

`agents/orchestrator.route_and_answer()` accepts `str | Sequence[UserContent]` for this reason:
a message with an image attached is a list like `["caption text", BinaryContent(...)]` (or just
`[BinaryContent(...)]` with no caption). `_message_text()`/`_has_attachment()` extract a
text-only view for the guardrail check and for `question_log` (which stores plain text — an
image-only message logs the placeholder `"[attached file]"`), while the *full* multimodal
content is still what gets sent to the LLM, so it can actually see the image.

**Limitations:** single generic demo student (no auth) — `question_log` is keyed by a constant
`student_id`, so the "asked by N students" rollup only reflects concurrent demo sessions, not a
real class roster. Output guardrail flags (`too_direct`) are computed but not currently
persisted or surfaced in the UI — see `agents/orchestrator.AgentAnswer.flagged` as the existing
extension point. Chat-attached images/files aren't persisted in session history — they apply to
the turn they're sent on; re-rendering `st.session_state`'s chat history after a rerun shows the
text only (see `capabilities/memory/session_memory.py`).

## Memory layers

1. **In-run** — handled by pydantic-ai's own message passing during a single agent run.
2. **Session** (`capabilities/memory/session_memory.py`) — `st.session_state`, gone when the
   tab closes. Only the *specialist* agent's messages are retained turn-to-turn (not the
   orchestrator's routing call), so next turn's context is the visible conversation, not the
   internal routing decision.
3. **Persistent, per-student** (`capabilities/memory/student_memory.py`) — SQLite, exposed to
   agents as a read-only tool (`check_if_repeated_question`) rather than always injected.
4. **Class-level aggregate** (`capabilities/memory/class_memory.py`) — rolls up
   `question_log` into the teacher-facing common-questions digest.
