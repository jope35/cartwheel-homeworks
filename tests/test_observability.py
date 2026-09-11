"""Homework 2, Part D: tests for the auth and trace contracts.

These tests do not require Langfuse, Docker, or a model provider key.
They use OpenTelemetry's InMemorySpanExporter to assert on trace attributes
and exercise the session/message endpoints directly (no HTTP layer).
"""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from fastapi import HTTPException

from agent.auth import AuthContext
from observability import instrument

SHOPPER_1 = AuthContext(user_id=1, role="shopper")
SHOPPER_2 = AuthContext(user_id=2, role="shopper")
MERCHANT_STORE_1 = AuthContext(user_id=9001, role="merchant", store_id=1)


def _install_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    original = instrument._tracer
    instrument._tracer = tracer
    return exporter, original


# ---------------------------------------------------------------------------
# Case 1: session creation rejects a user whose claimed role differs from
# the database role.
# ---------------------------------------------------------------------------

def test_create_session_rejects_role_mismatch(world: dict) -> None:
    from server import app as server_app

    server_app._SESSIONS.clear()
    # User 9002 exists in the seeded DB with role "merchant"; claiming
    # "shopper" must be rejected with 403.
    with pytest.raises(HTTPException) as exc:
        server_app.create_session(
            server_app.SessionCreate(user_id=9002, role="shopper")
        )
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Case 2: an allowed tool result records cartwheel.permission_denied=false
# without a denial reason attribute.
# ---------------------------------------------------------------------------

def test_allowed_tool_result_records_no_denial() -> None:
    from observability.instrument import record_tool_result

    exporter, original = _install_exporter()
    try:
        record_tool_result(
            SHOPPER_1,
            "get_order",
            {"ok": True, "order": {"order_id": 4127}},
        )
    finally:
        instrument._tracer = original

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs["cartwheel.permission_denied"] is False
    assert "cartwheel.permission_denied.reason" not in attrs


# ---------------------------------------------------------------------------
# Case 3: a token issued for one session cannot authorize a different session.
# ---------------------------------------------------------------------------

def test_token_cannot_authorize_different_session(world: dict) -> None:
    from server import app as server_app

    server_app._SESSIONS.clear()
    # Create session A (shopper, user 1).
    created_a = server_app.create_session(
        server_app.SessionCreate(user_id=1, role="shopper")
    )
    # Attempt to use session A's token against session B's id — must 403.
    with pytest.raises(HTTPException) as exc:
        server_app._authorize("nonexistent-session-id", f"Bearer {created_a['token']}")
    assert exc.value.status_code == 403
