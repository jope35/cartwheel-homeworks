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

from agents.tracing import set_trace_processors
from agents.tracing.processors import default_processor
from opentelemetry import trace

if TYPE_CHECKING:
    from agent.auth import AuthContext

REPO_ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("cartwheel.instrument")

_tracer = trace.get_tracer("cartwheel")

_genai_instrumented = False
_openai_tracing_enabled = False


def configure_model_tracing(*, openai_model: bool) -> None:
    """Remove implicit hosted export for non-OpenAI models.

    SDK processors are process-wide. Preserve either explicitly selected course
    destination; do not globally disable spans, which would also break Langfuse.
    """
    if not openai_model and not _genai_instrumented and not _openai_tracing_enabled:
        set_trace_processors([])


def setup_openai_tracing() -> bool:
    """Explicitly select hosted tracing, including for non-OpenAI inference."""
    global _openai_tracing_enabled
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError(
            "--trace-openai requires OPENAI_API_KEY; omit the flag for local chat"
        )
    set_trace_processors([default_processor()])
    _openai_tracing_enabled = True
    return True


def instrument_genai(tracer_provider: Any) -> None:
    """Install GenAI recording once, using the supplied OTel provider."""
    global _genai_instrumented
    if _genai_instrumented:
        return
    from opentelemetry.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    os.environ.setdefault("TRACELOOP_TRACE_CONTENT", "false")
    # Export only through Langfuse, not the SDK's separate hosted tracing path.
    instrumentor = OpenAIAgentsInstrumentor(replace_existing_processors=True)
    instrumentor.instrument(tracer_provider=tracer_provider)
    if not instrumentor.is_instrumented_by_opentelemetry:
        raise RuntimeError("OpenAI Agents tracing instrumentation failed to install")
    _genai_instrumented = True


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
        span.set_attribute("gen_ai.tool.name", tool_name)
        span.set_attribute("cartwheel.user_role", ctx.role)
        span.set_attribute("cartwheel.user_id", str(ctx.user_id))
        if ctx.store_id is not None:
            span.set_attribute("cartwheel.store_id", ctx.store_id)
        _set_permission_denied_attributes(span, result)


def _set_permission_denied_attributes(span: trace.Span, result: dict[str, Any]) -> None:
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
    denied = result.get("error") == "permission_denied"
    span.set_attribute("cartwheel.permission_denied", denied)
    if denied:
        span.set_attribute(
            "cartwheel.permission_denied.reason", result.get("reason", "")
        )
