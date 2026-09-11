# Cartwheel course repository

The repository contains the Cartwheel support agent and the student work for all five modules of "Evaluating and Improving AI Agents." Cartwheel is a fictional commerce platform that hosts independent stores. Students begin by completing the agent, then use the same repository for trace analysis, automated evaluation, continuous integration, adversarial evaluation, and improvement experiments.

Begin with the [homework index](homework/README.md). Each assignment names the code and records required for the corresponding module.

## Setup

You need Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env          # then fill in the keys you have
uv run python -m seed.generate
uv run pytest
uv run python -m agent.cli --role shopper
```

The repository supports OpenAI, Anthropic, and Together AI models. You need a
key for only one provider. Choose the model with the CLI's `--model` flag or
the `CARTWHEEL_MODEL` environment variable. The tests need no model key.

The default development seed is the executable course world: 20 stores, 800
products, 525 users, 10,000 orders, and 18 policy documents. The seed script
is deterministic. Two runs produce identical data, and the
three demo orders from lecture (#4127, #3980, #4455, all owned by shopper
user 1) always come out the same. The seed also inserts six documented data
quality defects for challenge scenarios. Their identifiers and expected
handling are stored in the `data_quality_cases` table.

For Lecture 2 you will also start the tracing stack:

```bash
docker compose -f observability/docker-compose.yml up -d
```

and serve the agent behind the endpoint:

```bash
uv run uvicorn server.app:app --port 8010
```

## Repo map

```
CLAUDE.md                 workspace config for your coding agent
SPEC.md                   support specification: scope, access matrix, criteria table
facts.yaml                the facts sheet; every policy number lives here
data/
  policies/*.md           policy corpus, rendered from facts.yaml by the seed
  cartwheel.db            stores, products, users, orders (gitignored; run the seed)
seed/
  generate.py             deterministic world generator (--scale dev|full)
  eligibility.py          the pure refund-eligibility function (the test oracle)
  policies.py             policy-doc templates
  validate.py             checks every number in every doc against facts.yaml
agent/                    support agent scaffold
  agent.py                system prompt, model wiring, the three lecture tools
  tools.py                HOMEWORK 1: five tool holes
  auth.py                 auth context + permission checks (complete; do not weaken)
  db.py                   typed SQLite access layer (complete)
  helpcenter.py           policy corpus loading + BM25 (complete)
  cli.py                  chat shell (complete)
server/
  app.py                  HOMEWORK 2: session + message routes; token helpers provided
observability/
  docker-compose.yml      self-hosted Langfuse (web, worker, postgres, clickhouse, redis, minio)
  instrument.py           tracing setup (provided) + HOMEWORK 2: tool-result spans
scenarios/
  skill/SKILL.md          instructions that a coding agent follows to generate scenarios
  validate.py             executable schema and final-dataset checks
  runner.py               plays scenario JSONL against the endpoint (complete)
  export_langfuse.py      exports complete scenario traces for Module 2
  atif_export.py          optional ATIF reader extension
analysis/                 MODULE 2: review interface, helper functions, and judge records
eval_cases/               MODULE 3: reviewed regression and capability cases
tests/eval/               MODULE 3: unit, integration, and end to end evaluation tests
replay/                   MODULE 3: repeated evaluation case execution
monitoring/               MODULE 3: sampling, corrected rates, and score writing
agent/guards.py           MODULE 4: input, output, and tool guards
agent/approvals.py        MODULE 4: refund approval and audit records
promptfooconfig.yaml      MODULE 4: automated adversarial evaluation
reports/
  smoke.sql               smoke-report queries against the trace store
homework/                 student assignments for Modules 1 to 5
tests/                    offline, no API keys; homework tests are xfail until done
```

## Which files are homework

| Homework | File | Holes |
| --- | --- | --- |
| HW1 | `agent/tools.py` | `get_policy`, `search_products`, `list_my_orders`, `cancel_order`, `find_order` |
| HW2 | `observability/instrument.py` | `record_tool_result`, `_set_permission_denied_attributes` |
| HW2 | `server/app.py` | `create_session`, `post_message` |

Every required homework hole is marked `### YOUR CODE HERE (HWn)`, has a docstring precise
enough to implement from, and has a matching test in
`tests/test_hw_holes.py` that is xfail until you implement it. Run them
with `uv run pytest tests/test_hw_holes.py`.

The Module 1 handouts are in `homework/module-1/`. The [homework index](homework/README.md) lists all released assignments. A [video walkthrough](https://youtu.be/qO98jDayTHo?si=gLN5FZ3FDiAIs_gG) of how to attempt Homework 1 is also available.

