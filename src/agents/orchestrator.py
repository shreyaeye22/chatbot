"""Routes each message to the right specialist agent based on intent.

This is the single entry point the UI calls (`route_and_answer`). It also
owns the parts that must happen deterministically regardless of what the
model does: running input/output guardrails, falling back to escalation on
any agent failure or bad routing output, and logging every question.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Literal, Sequence

from pydantic import BaseModel
from pydantic_ai import Agent, ModelResponse, ToolCallPart, UserContent
from pydantic_ai.usage import RunUsage

from agents.concept_agent import concept_agent
from agents.deps import AgentDeps
from agents.escalation_agent import escalation_agent
from agents.logistics_agent import logistics_agent
from capabilities.memory.student_memory import record_question
from config.settings import format_subject_list, get_model, get_model_settings
from data.db import get_connection
from toolsets import escalation_tools, guardrail_tools

logger = logging.getLogger(__name__)

Route = Literal["logistics", "concept", "escalation"]

SPECIALISTS = {
    "logistics": logistics_agent,
    "concept": concept_agent,
    "escalation": escalation_agent,
}


class RouteDecision(BaseModel):
    route: Route
    reason: str


ORCHESTRATOR_SYSTEM_PROMPT = f"""
You route a Grade 9 MYP student's message to the right specialist. Choose exactly one route:

- "logistics": questions about homework deadlines, assessment/test dates, what's due, or what
  an assignment's instructions mean.
- "concept": questions asking to explain, understand, or get help with a concept or how to solve
  a type of problem, in any of {format_subject_list()}.
- "escalation": anything else, or anything you are not confident fits the other two categories.

Always return exactly one route and a short reason.
"""

orchestrator_agent = Agent(
    model=None,
    deps_type=AgentDeps,
    output_type=RouteDecision,
    system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
)

OFF_TOPIC_REPLY = (
    f"That looks unrelated to your {format_subject_list()} work — I can help with homework "
    "deadlines, assessment dates, assignment instructions, or explaining a concept from class. "
    "Try asking about one of those!"
)

GREETING_REPLY = "Hello! How can I help you today?"

ESCALATION_FALLBACK_REPLY = (
    "I couldn't confidently answer that, so I've flagged it for your teacher to follow up on. "
    "In the meantime, try checking ManageBac/Teams or asking a classmate."
)


@dataclass
class AgentAnswer:
    text: str
    route: str
    new_messages: list = field(default_factory=list)
    flagged: bool = False
    tool_calls: list[dict] = field(default_factory=list)


def _message_text(user_message: str | Sequence[UserContent]) -> str:
    """The plain-text portion of a message, joining text parts if it's multimodal."""
    if isinstance(user_message, str):
        return user_message
    return " ".join(part for part in user_message if isinstance(part, str)).strip()


def _has_attachment(user_message: str | Sequence[UserContent]) -> bool:
    return not isinstance(user_message, str) and any(
        not isinstance(part, str) for part in user_message
    )


def _tool_calls(new_messages: list) -> list[dict]:
    """Every tool the specialist agent actually invoked this turn, in call order.

    Surfaced to the UI (ui.components.render_tool_trace) so a student/teacher can see
    what the assistant did, not just its final answer.
    """
    calls = []
    for message in new_messages:
        if not isinstance(message, ModelResponse):
            continue
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                calls.append({"tool": part.tool_name, "args": part.args_as_dict()})
    return calls


def _log_usage(label: str, usage: RunUsage | None) -> None:
    """Log token/cache-token counts and estimated cost for one or more LLM calls.

    `usage.cost` is computed by pydantic-ai (via genai-prices) from the model/provider
    and token counts, so this doesn't need its own pricing table - and stays `None`
    (logged as "unknown") rather than silently wrong if a model can't be priced.
    """
    if usage is None:
        return
    cost = f"${usage.cost:.4f}" if usage.cost is not None else "unknown"
    logger.info(
        "%s usage: input=%d (cache_read=%d, cache_write=%d) output=%d requests=%d cost=%s",
        label,
        usage.input_tokens,
        usage.cache_read_tokens,
        usage.cache_write_tokens,
        usage.output_tokens,
        usage.requests,
        cost,
    )


def _run_agent_safely(
    agent: Agent,
    prompt: str | Sequence[UserContent],
    *,
    deps: AgentDeps,
    model,
    model_settings=None,
    message_history,
):
    try:
        result = agent.run_sync(
            prompt,
            deps=deps,
            model=model,
            model_settings=model_settings,
            message_history=message_history,
        )
        return result.output, result.new_messages(), result.usage, None
    except Exception as exc:  # small/free models can time out, rate-limit, or mis-format output
        return None, [], None, exc


def route_and_answer(
    user_message: str | Sequence[UserContent],
    deps: AgentDeps,
    *,
    message_history: list | None = None,
    model=None,
    model_settings=None,
) -> AgentAnswer:
    model = model or get_model()
    model_settings = model_settings if model_settings is not None else get_model_settings()
    message_history = message_history or []

    message_text = _message_text(user_message)
    # A caption's wording can't be judged against the on-topic keyword list the way a
    # student-attached worksheet photo/file can't - an attachment is itself a strong
    # on-topic signal that a plain keyword check on the caption text would miss.
    guardrail = guardrail_tools.check_input_message(message_text)
    if _has_attachment(user_message):
        guardrail = replace(guardrail, off_topic=False)

    log_text = message_text or "[attached file]"

    conn = get_connection(deps.db_path)
    try:
        if guardrail.is_greeting:
            logger.info("greeting-only message answered directly")
            record_question(
                conn,
                student_id=deps.student_id,
                question=log_text,
                route="greeting",
                answered=True,
            )
            return AgentAnswer(text=GREETING_REPLY, route="greeting")

        if guardrail.off_topic:
            logger.info("off-topic question rejected by input guardrail")
            record_question(
                conn,
                student_id=deps.student_id,
                question=log_text,
                route="off_topic",
                answered=True,
            )
            return AgentAnswer(text=OFF_TOPIC_REPLY, route="off_topic")

        decision, _, routing_usage, routing_error = _run_agent_safely(
            orchestrator_agent,
            user_message,
            deps=deps,
            model=model,
            model_settings=model_settings,
            message_history=message_history,
        )
        _log_usage("orchestrator", routing_usage)
        if routing_error is not None:
            logger.warning("routing call failed, defaulting to escalation", exc_info=routing_error)
        route: Route = decision.route if decision is not None else "escalation"
        if decision is not None:
            logger.info("routed to %s (%s)", route, decision.reason)

        text, new_messages, specialist_usage, error = _run_agent_safely(
            SPECIALISTS[route],
            user_message,
            deps=deps,
            model=model,
            model_settings=model_settings,
            message_history=message_history,
        )
        _log_usage(route, specialist_usage)

        turn_usage = routing_usage
        if specialist_usage is not None:
            turn_usage = specialist_usage if turn_usage is None else turn_usage + specialist_usage
        _log_usage("turn total", turn_usage)

        flagged = False
        if error is not None or not text:
            if error is not None:
                logger.warning("%s agent failed, falling back to escalation", route, exc_info=error)
            else:
                logger.warning("%s agent returned an empty answer, falling back to escalation", route)
            text = ESCALATION_FALLBACK_REPLY
            new_messages = []
            route = "escalation"
        elif route == "concept":
            flagged = guardrail_tools.check_concept_answer(text).too_direct
            if flagged:
                logger.warning("concept answer flagged as too direct by output guardrail")

        if route == "escalation":
            escalation_tools.log_unanswered_question(
                conn, student_id=deps.student_id, question=log_text
            )
        else:
            record_question(
                conn,
                student_id=deps.student_id,
                question=log_text,
                route=route,
                answered=True,
            )

        return AgentAnswer(
            text=text,
            route=route,
            new_messages=new_messages,
            flagged=flagged,
            tool_calls=_tool_calls(new_messages),
        )
    finally:
        conn.close()
