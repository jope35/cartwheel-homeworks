# Homework 2, implementing the traced agent endpoint

Homework 2 asks you to expose the support agent through an authenticated HTTP endpoint and instrument its execution with OpenTelemetry. You will use the resulting traces to verify which identity reached the tools and where a permission denial occurred.

## Expected work

- Estimated time: 4 to 6 hours.
- Expected production code: approximately 60 to 80 lines in `server/app.py` and `observability/instrument.py`.
- Expected test code: approximately 30 to 50 lines in `tests/test_observability.py`.
- Expected total code: approximately 90 to 130 lines.
- Other work: at least five traced requests, two trace records in JSON, and a video of no more than 5 minutes.

The estimate assigns most of the time to implementing and testing the endpoint. Starting Docker is necessary setup, but it is not counted as substantive programming work.

## Preparation

Read the following files before editing code:

- `server/app.py`, which provides request models and token helpers.
- `observability/instrument.py`, which configures OpenTelemetry and Langfuse.
- `agent/auth.py`, which defines the authenticated context passed to tools.
- `_call` in `agent/agent.py`, which invokes `record_tool_result` after every tool call.

The token implementation is suitable only for local development. The provided token allows the endpoint to distinguish identity supplied by the server from identity claimed in a conversation.

Before implementing anything, run the homework tests so you can see which cases exist and what a failing run looks like:

```bash
uv run pytest --runxfail -vv tests/test_hw_holes.py -k hw2
```

All tests should fail or be marked xfail at this point. You will run the same command after each part to confirm progress.

## Part A, record structured tool results

Every tool call the agent makes should leave a structured trace record so that later evaluations can query what happened without parsing prose. In this part you wire that recording into the instrumentation layer.

Implement `record_tool_result` and `_set_permission_denied_attributes` in `observability/instrument.py`.

For every recorded tool result, create a child span named `cartwheel.tool_result`. The span must contain:

- `gen_ai.tool.name`
- `cartwheel.user_role`, as a string
- `cartwheel.user_id`, as the decimal user identifier stored in a string
- `cartwheel.store_id`, as an integer when the caller is a merchant
- `cartwheel.permission_denied`, as a Boolean value
- `cartwheel.permission_denied.reason`, when permission was denied

The span attributes have different purposes. The `gen_ai.*` attribute uses a conventional namespace recognized by other observability systems. The `cartwheel.*` attributes describe facts about Cartwheel queried by later evaluations.

After implementing, run the Part A tests:

```bash
uv run pytest --runxfail -vv tests/test_hw_holes.py -k "tool_result_span_attributes or permission_denied_attribute"
```

## Part B, implement session creation

The agent needs an authenticated caller before it can enforce access control. In this part you build the session creation endpoint that validates a user's identity against the database and issues a signed token.

Implement `create_session` in `server/app.py`. The endpoint must:

- Reject an unknown role with HTTP 400.
- Load the requested user from the database.
- Reject an unknown user identifier with HTTP 404.
- Reject a role different from the user's stored role with HTTP 403.
- Create an `AuthContext` from the stored identity.
- Store the context and its `SQLiteSession` in `_SESSIONS`.
- Return a session identifier and a signed token with HTTP 200.

The signed token must contain `session_id`, `user_id`, `role`, `store_id`, and `issued_at`, using the verified database identity. Do not construct the authorization context from later chat messages.

After implementing, run the session creation test:

```bash
uv run pytest --runxfail -vv tests/test_hw_holes.py -k "create_session_binds"
```

## Part C, implement the traced message endpoint

With sessions in place, you can now accept user messages over HTTP. The message endpoint ties together authentication, the agent loop, and tracing so that every request produces a fully attributed trace.

Implement `post_message` in `server/app.py`. The endpoint must authorize the bearer token before it runs the agent. The authorization checks are already provided in `_authorize`: a missing or invalid token returns HTTP 401, a token issued for a different session returns HTTP 403, and an unknown session returns HTTP 404. The endpoint must then recover the session stored by the server and compute the version of the rendered system prompt.

Run the agent inside a root span named `cartwheel.session_message`. Record the following attributes on the root span:

- `cartwheel.user_role`
- `cartwheel.user_id`, as the decimal user identifier stored in a string
- `cartwheel.prompt_version`
- `cartwheel.scenario_id`, when the request supplies a nonempty value

Return the session identifier, final reply, and prompt version. The OpenInference instrumentation will create the nested model and tool spans; do not reproduce the generated spans manually.

After implementing, run the message endpoint test:

```bash
uv run pytest --runxfail -vv tests/test_hw_holes.py -k "message_endpoint_records_root_span"
```

At this point all four hw2 tests should pass:

```bash
uv run pytest --runxfail -vv tests/test_hw_holes.py -k hw2
```

## Part D, test the authentication and trace contracts

The supplied tests verify the provided contract, but they do not cover every authentication edge case. Writing your own tests forces you to think through the boundary conditions that the endpoint must handle and confirms that the trace attributes are set correctly for each case.

Create `tests/test_observability.py`. Add tests for the following cases:

- Session creation rejects a user whose claimed role differs from the database role.
- An allowed tool result records `cartwheel.permission_denied = false` without a denial reason.
- A token issued for one session cannot authorize a different session.

Use OpenTelemetry's `InMemorySpanExporter` for span assertions. The tests must not require Langfuse, Docker, or a model provider key.

Run the supplied contract tests:

```bash
uv run pytest --runxfail tests/test_hw_holes.py -k hw2
```

Then run your tests and the complete suite:

```bash
uv run pytest tests/test_observability.py
uv run pytest
```

## Part E, run the endpoint and inspect traces

Parts A through D verified the implementation offline. In this part you run the full stack, send real requests, and confirm that structured traces appear in the local Langfuse dashboard.

If you have not created `.env`, copy `.env.example` to `.env` and add one model provider key. Do not overwrite an existing `.env`. Verify that the three `LANGFUSE_*` values from `.env.example` are also present. You do not need a Langfuse Cloud account; the Docker Compose file runs a local Langfuse instance, and the `.env.example` values point at it.

If you previously set `LANGFUSE_*` variables in your shell profile or environment, those values take precedence over `.env` because the loader uses `os.environ.setdefault`. Either unset them or make sure they match the local instance. A common symptom of a mismatch is that requests return HTTP 200 but no traces appear in the local dashboard.

Docker with Compose is required for the local trace stack.

Start Langfuse and the agent server in separate terminals:

```bash
docker compose -f observability/docker-compose.yml up -d
uv run uvicorn server.app:app --port 8010
```

Open `http://localhost:3000`, then sign in as `student@example.com` with the password `cartwheel-dev-pass`.

Create a session with an HTTP client:

```bash
curl -s -X POST http://localhost:8010/sessions \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"role":"shopper"}'
```

Copy the returned session identifier and token into a message request:

```bash
curl -s -X POST http://localhost:8010/sessions/SESSION_ID/messages \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer TOKEN' \
  -d '{"message":"Show me order 4127."}'
```

Submit at least five requests drawn from `hw1-session.jsonl`. Create a separate merchant session with `{"user_id":9002,"role":"merchant"}` for the request concerning order `4127`; a token from the shopper session cannot represent the merchant. Ask the agent to look up order `4127`, then confirm that the trace contains a `cartwheel.tool_result` span whose `cartwheel.permission_denied` attribute is `true`. A prose refusal without the structured tool result does not satisfy the requirement; repeat the request with explicit lookup wording if the model refuses before calling the tool.

## Part F, compare two prompt versions

Module 2 will use prompt version hashes to group traces by the prompt that produced them. In this part you confirm that the instrumentation captures the version and that a prompt change produces a different hash, establishing the baseline for later comparisons.

This part requires the prompt revision you made in Homework 1. If you did not revise the prompt in Homework 1, make a small, deliberate change to the system prompt now (for example, add an explicit instruction for the agent to escalate refund requests to a human) and treat the changed version as the "revised" prompt for the comparison below.

Find the `cartwheel.prompt_version` attribute for the motivating failed exchange from Homework 1. Save the exact revised text, then stop the server.

Temporarily restore the earlier prompt text and restart the server. Restarting uvicorn clears all in-memory sessions, so you must create a new session and token before sending the request. Submit the same request with the same authenticated user. Verify a change in `cartwheel.prompt_version`, then restore the Homework 1 revision.

The comparison is interpretable only when the prompt edit is the sole intended change between the two runs.

## Trace record

Choose two traces you can explain from the root span through the final response:

- One trace containing a write tool or an escalation tool.
- One trace containing a permission denial.

Create `hw2-traces.json` as a JSON array containing exactly two objects. For each trace, record:

- `trace_id`
- `permalink`
- `prompt_version`
- `user_role`
- `user_id`
- `tool_order`, as an ordered list of tool names
- `final_status`, with the value `completed` or `error`

## Files to commit

- `observability/instrument.py`
- `server/app.py`
- `tests/test_observability.py`
- `hw2-traces.json`, containing the two selected traces

## Video

Record one continuous screen video of no more than 5 minutes. In the recording:

- Run one endpoint or instrumentation test.
- Read both selected traces from the root span to the final response.
- Explain how the endpoint established the authenticated identity.
- Show the tool result span recording the permission denial.
- Show the two prompt version hashes produced by the controlled comparison.
- Regenerate the span count for one selected trace.
