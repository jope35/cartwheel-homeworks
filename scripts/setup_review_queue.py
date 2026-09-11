"""Create the HW1 Part B review queue and its label schemas (idempotent).

Run this after recording Part B conversations with ``--mlflow`` so the
traces exist in the ``hw1-part-b`` experiment. Re-running is safe:
existing schemas and the queue are reused, and re-adding a trace keeps
its review status.

Usage:
    uv run python scripts/setup_review_queue.py
"""

from __future__ import annotations

import mlflow
from mlflow.genai.label_schemas import (
    InputCategorical,
    InputPassFail,
    InputText,
    create_label_schema,
    delete_label_schema,
    get_label_schema,
)
from mlflow.genai.label_schemas import validation as _validation
from mlflow.genai.review_queues import (
    add_items_to_review_queue,
    create_review_queue,
    list_review_queues,
    list_review_queue_items,
    remove_items_from_review_queue,
    update_review_queue,
)

EXPERIMENT = "hw1-part-b"
QUEUE_NAME = "HW1 Part B - Conversation Review"

REQUIREMENT_IDS = [
    "PURPOSE-1",
    "SCOPE-1",
    "SCOPE-2",
    "AUTH-1",
    *[f"TOOL-{n}" for n in range(1, 10)],
    *[f"ESC-{n}" for n in range(1, 5)],
    *[f"RESP-{n}" for n in range(1, 6)],
]

SCHEMAS = [
    dict(
        name="expected_matches_spec",
        type="feedback",
        input=InputPassFail(positive_label="Matches", negative_label="Does not match"),
        instruction="Does the recorded expected behavior match SPEC.md?",
    ),
    dict(
        name="met_requirement",
        type="feedback",
        input=InputPassFail(positive_label="Met", negative_label="Not met"),
        instruction="Did the observed behavior meet the requirement?",
    ),
    dict(
        name="problem_source",
        type="feedback",
        input=InputCategorical(options=["prompt", "tool", "specification", "none"]),
        instruction="If it did not meet the requirement, where did the problem originate?",
    ),
    dict(
        name="requirement_id",
        type="feedback",
        input=InputCategorical(options=REQUIREMENT_IDS),
        instruction="Which SPEC.md requirement applies?",
    ),
    dict(
        name="comment",
        type="feedback",
        input=InputText(),
        instruction="Notes for the student.",
    ),
]


def ensure_schema(experiment_id: str, spec: dict) -> str:
    """Return the schema_id for spec['name'], reusing or replacing an existing schema."""
    try:
        existing = get_label_schema(name=spec["name"], experiment_id=experiment_id)
    except Exception:
        existing = None
    if existing is not None:
        if type(existing.input) is type(spec["input"]):
            print(f"  schema '{spec['name']}' exists, reusing {existing.schema_id}")
            return existing.schema_id
        delete_label_schema(schema_id=existing.schema_id)
        print(f"  schema '{spec['name']}' had a different input type, deleted")
    schema = create_label_schema(**spec, experiment_id=experiment_id)
    print(f"  created schema '{spec['name']}' ({schema.schema_id})")
    return schema.schema_id


def ensure_queue(experiment_id: str, schema_ids: list[str]):
    """Return the review queue, reusing an existing queue with the same name."""
    for queue in list_review_queues(experiment_id=experiment_id):
        if queue.name == QUEUE_NAME:
            if set(queue.schema_ids) != set(schema_ids):
                items = [i.item_id for i in list_review_queue_items(queue.queue_id)]
                if items:
                    remove_items_from_review_queue(queue.queue_id, item_ids=items)
                queue = update_review_queue(queue.queue_id, schema_ids=schema_ids)
                print(f"  queue '{QUEUE_NAME}' schema set updated")
            print(f"  queue '{QUEUE_NAME}' exists ({queue.queue_id})")
            return queue
    queue = create_review_queue(
        name=QUEUE_NAME,
        queue_type="custom",
        schema_ids=schema_ids,
        experiment_id=experiment_id,
    )
    print(f"  created queue '{QUEUE_NAME}' ({queue.queue_id})")
    return queue


def add_all_traces(queue_id: str, experiment_id: str) -> None:
    traces = mlflow.search_traces(locations=[experiment_id])
    item_ids = list(traces["trace_id"])
    if not item_ids:
        print("  no traces found; record sessions with --mlflow first")
        return
    add_items_to_review_queue(queue_id, item_ids=item_ids)
    print(f"  added {len(item_ids)} trace(s) to the queue")


def main() -> None:
    mlflow.set_experiment(EXPERIMENT)
    experiment = mlflow.get_experiment_by_name(EXPERIMENT)
    if experiment is None:
        raise SystemExit(f"experiment '{EXPERIMENT}' does not exist")
    experiment_id = experiment.experiment_id

    # ponytail: SDK validates InputCategorical.options at create time against a
    # 10-entry constant; patch it for this local store run so one dropdown can
    # hold all SPEC.md requirement IDs. Revisit if tracking moves to a server.
    _validation.CATEGORICAL_OPTIONS_MAX_COUNT = len(REQUIREMENT_IDS)

    schema_ids = [ensure_schema(experiment_id, spec) for spec in SCHEMAS]
    queue = ensure_queue(experiment_id, schema_ids)
    add_all_traces(queue.queue_id, experiment_id)


if __name__ == "__main__":
    main()