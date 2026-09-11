"""Tracing setup and the hand-written instrumentation for Homework 2.

`setup_tracing()` is the whole course stack: the Langfuse client reads
LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST from the
environment and registers an OpenTelemetry tracer provider, and the
OpenInference instrumentor makes the Agents SDK emit spans through it. That
is the promised ~3 lines. Everything else in this file is the one seam
students hand-roll: auth context and permission-denied events as span
attributes (the `cartwheel.*` namespace from the Module 1 outline,
Artifact G).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from opentelemetry import trace

if TYPE_CHECKING:
    from agent.auth import AuthContext

REPO_ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("cartwheel.instrument")

_tracer = trace.get_tracer("cartwheel")


def load_env(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env into os.environ (existing vars win).

    A tiny loader so the repo does not need python-dotenv. Lines starting
    with '#' and blank lines are ignored. Values are never logged.
    """
    path = path or REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and value:
            os.environ.setdefault(key, value)


def setup_tracing() -> None:
    """Instrument the Agents SDK and ship spans to self-hosted Langfuse."""
    load_env()
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        log.warning(
            "LANGFUSE_PUBLIC_KEY is not set; tracing is off. Start the stack "
            "(docker compose -f observability/docker-compose.yml up -d) and "
            "copy .env.example to .env."
        )
        return
    # The course setup, as promised: about three lines.
    from langfuse import get_client
    from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    get_client()  # registers the OTel tracer provider from LANGFUSE_* env vars
    OpenAIAgentsInstrumentor().instrument()
    log.info("tracing enabled; spans go to %s", os.environ.get("LANGFUSE_HOST"))


def setup_mlflow_tracing() -> None:
    """Record the session's model and tool calls as MLflow traces (HW1 Part B).

    Writes to the local ``mlflow.db`` store under the ``hw1-part-b`` experiment
    that scripts/setup_review_queue.py reads. ``mlflow.openai.autolog()`` covers
    the OpenAI Agents SDK (including its tool calls); ``mlflow.litellm.autolog()``
    covers the non-OpenAI course models routed through LiteLLM. View traces with
    ``uv run mlflow ui --backend-store-uri sqlite:///mlflow.db``.
    """
    load_env()
    import mlflow

    mlflow.set_tracking_uri(f"sqlite:///{REPO_ROOT / 'mlflow.db'}")
    mlflow.set_experiment("hw1-part-b")
    mlflow.openai.autolog()
    mlflow.litellm.autolog()
    log.info("MLflow tracing enabled; traces go to %s", mlflow.get_tracking_uri())


def record_tool_result(
    ctx: "AuthContext", tool_name: str, result: dict[str, Any]
) -> None:
    """Attach auth context and permission-denied attributes to the trace.

    Called by every tool wrapper in agent/agent.py after the tool logic runs.
    It emits one small child span (named "cartwheel.tool_result") under the
    current trace carrying the `cartwheel.*` attributes, so Module 2 can
    query who the caller was and Module 4 can find every permission denial.

    If tracing is not configured, the span is non-recording and this function
    remains a no-op. The early return keeps the uninstrumented agent usable
    before Homework 2 is complete.
    """
    with _tracer.start_as_current_span("cartwheel.tool_result") as span:
        if not span.is_recording():
            return
        ### YOUR CODE HERE (HW2)
        raise NotImplementedError(
            "HW2: record the tool name, authenticated caller, and denial attributes"
        )


def _set_permission_denied_attributes(
    span: trace.Span, result: dict[str, Any]
) -> None:
    """Set the permission-denied attributes on a tool-result span.

    Contract (Module 1 outline, Artifact G):
      - `result` is the structured dict a tool returned (see agent/auth.py
        for the convention).
      - Always set the span attribute "cartwheel.permission_denied" to a
        bool: True when result["error"] == "permission_denied", else False.
        Use result.get, since success dicts have no "error" key.
      - When it is True, also set "cartwheel.permission_denied.reason" to
        result["reason"] (default to "" if the reason is missing).
      - Set attributes with span.set_attribute(name, value). Do not raise on
        odd input; any dict without the permission_denied error code is
        simply False.

    Why this exists: permission-denied events are gold for Module 4, and
    the smoke report counts them and Module 3 asserts on them. This is the one place in the
    course where you touch instrumentation by hand.
    """
    ### YOUR CODE HERE (HW2)
    raise NotImplementedError("HW2: set the cartwheel.permission_denied span attribute")
