"""Routes each message to the right specialist agent based on intent.

This is the single entry point the UI calls (`route_and_answer`). It also
owns the parts that must happen deterministically regardless of what the
model does: running input/output guardrails, falling back to escalation on
any agent failure or bad routing output, and logging every question.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent

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


def _run_agent_safely(
    agent: Agent, prompt: str, *, deps: AgentDeps, model, model_settings=None, message_history
):
    try:
        result = agent.run_sync(
            prompt,
            deps=deps,
            model=model,
            model_settings=model_settings,
            message_history=message_history,
        )
        return result.output, result.new_messages(), None
    except Exception as exc:  # small/free models can time out, rate-limit, or mis-format output
        return None, [], exc


def route_and_answer(
    user_message: str,
    deps: AgentDeps,
    *,
    message_history: list | None = None,
    model=None,
    model_settings=None,
) -> AgentAnswer:
    model = model or get_model()
    model_settings = model_settings if model_settings is not None else get_model_settings()
    message_history = message_history or []

    guardrail = guardrail_tools.check_input_message(user_message)

    conn = get_connection(deps.db_path)
    try:
        if guardrail.off_topic:
            logger.info("off-topic question rejected by input guardrail")
            record_question(
                conn,
                student_id=deps.student_id,
                question=user_message,
                route="off_topic",
                answered=True,
            )
            return AgentAnswer(text=OFF_TOPIC_REPLY, route="off_topic")

        decision, _, routing_error = _run_agent_safely(
            orchestrator_agent,
            user_message,
            deps=deps,
            model=model,
            model_settings=model_settings,
            message_history=message_history,
        )
        if routing_error is not None:
            logger.warning("routing call failed, defaulting to escalation", exc_info=routing_error)
        route: Route = decision.route if decision is not None else "escalation"
        if decision is not None:
            logger.info("routed to %s (%s)", route, decision.reason)

        text, new_messages, error = _run_agent_safely(
            SPECIALISTS[route],
            user_message,
            deps=deps,
            model=model,
            model_settings=model_settings,
            message_history=message_history,
        )

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
                conn, student_id=deps.student_id, question=user_message
            )
        else:
            record_question(
                conn,
                student_id=deps.student_id,
                question=user_message,
                route=route,
                answered=True,
            )

        return AgentAnswer(text=text, route=route, new_messages=new_messages, flagged=flagged)
    finally:
        conn.close()
