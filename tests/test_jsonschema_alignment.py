"""Parity check between the JSON Schemas and the Pydantic bindings.

Both layers must agree on what is acceptable. If a payload is accepted by one
and rejected by the other, the contract has drifted between the
language-neutral source of truth (``schemas/*.json``) and the Python binding
(``messages.py``) — a class of bug we cannot afford between worker and API.

* What it can't reproduce — the cross-field validator. Look at CompletionMessage._check_status_fields
(image_gen_contract/messages.py:103). The rule is: when status == "completed", the message MUST have output_images,
model_version, processing_seconds, and MUST NOT have failure_reason; when status == "failed", the inverse. The JSON Schema
almost expresses this with the allOf / if / then block in completion.json, but only the "required when" half — it doesn't say
"must NOT be present when status='completed'" for failure_reason, or "must be empty/omitted when status='failed'" for
output_images. And even the parts that are in JSON Schema, datamodel-codegen translates if/then/required imperfectly into
Pydantic — typically you get all those fields as Optional with no enforcement of the conditional. The hand-written
model_validator(mode="after") enforces the full bidirectional rule precisely.

* What it can't reproduce — the tuned error messages. The hand-written validators raise specific strings:
- "gcs_uri must be gs://<bucket>/<object>"
- "output_prefix must be gs://<bucket>/<dir>/ (trailing slash)"
- "callback_topic must be projects/<project>/topics/<name>"

Those exact substrings are asserted by pytest.raises(ValidationError, match="gcs_uri") etc. across the consumer test suites.
A codegen tool produces a generic pattern regex check whose error message looks like "String should match pattern
'^gs://[^/]+/.+'" — which fails the existing match="gcs_uri" assertions and is also less helpful when a real failure shows up
in logs.

* The compromise I chose. Three things, working together:

- image_gen_contract/schemas/{job,completion}.json — language-neutral source of truth. Anyone (Dart client, TS bindings, a
separate Go service, schema viewer) can read these without touching Python.
- image_gen_contract/messages.py — the Python binding, hand-written. It carries the cross-field rule and the tuned messages.
This is what both repos import.
- tests/test_jsonschema_alignment.py — runs every fixture through both the JSON Schema (via the jsonschema library) and the
Pydantic model. If one accepts a payload the other rejects, the test fails. That's the safety net that catches drift between
the two — e.g., if someone adds a field to messages.py and forgets to add it to job.json, the parity test goes red.
"""

from __future__ import annotations

import jsonschema
import pytest
from pydantic import ValidationError

from image_gen_contract import CompletionMessage, JobMessage, load_schema


def _accepted_by_jsonschema(schema: dict, payload: dict) -> bool:
    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError:
        return False
    return True


def _accepted_by_pydantic(model_cls, payload: dict) -> bool:
    try:
        model_cls.model_validate(payload)
    except ValidationError:
        return False
    return True


# --- load_schema --------------------------------------------------------------


def test_load_schema_returns_dict_with_id() -> None:
    job = load_schema("job")
    completion = load_schema("completion")

    assert job["title"] == "ImageGenJob"
    assert completion["title"] == "ImageGenCompletion"
    assert job["$id"].endswith("/job.json")
    assert completion["$id"].endswith("/completion.json")


# --- positive parity (both accept the canonical fixtures) ---------------------


def test_pydantic_and_jsonschema_both_accept_valid_job(valid_job) -> None:
    schema = load_schema("job")
    assert _accepted_by_jsonschema(schema, valid_job)
    assert _accepted_by_pydantic(JobMessage, valid_job)


def test_pydantic_and_jsonschema_both_accept_valid_completed(valid_completed) -> None:
    schema = load_schema("completion")
    assert _accepted_by_jsonschema(schema, valid_completed)
    assert _accepted_by_pydantic(CompletionMessage, valid_completed)


def test_pydantic_and_jsonschema_both_accept_valid_failed(valid_failed) -> None:
    schema = load_schema("completion")
    assert _accepted_by_jsonschema(schema, valid_failed)
    assert _accepted_by_pydantic(CompletionMessage, valid_failed)


def test_pydantic_and_jsonschema_both_accept_valid_panel_completed(
    valid_panel_completed,
) -> None:
    schema = load_schema("completion")
    assert _accepted_by_jsonschema(schema, valid_panel_completed)
    assert _accepted_by_pydantic(CompletionMessage, valid_panel_completed)


# --- negative parity (both reject the same kinds of bad payload) -------------


@pytest.mark.parametrize(
    "mutation",
    [
        {"schema_version": 99},
        {"surprise": "extra"},
        {"input_photos": []},
        {"output_count": 0},
        {"output_count": 17},
        {"output_prefix": "/local/path/"},
        {"callback_topic": "topic-name"},
    ],
)
def test_invalid_job_rejected_by_both_layers(valid_job, mutation) -> None:
    schema = load_schema("job")
    payload = valid_job | mutation
    assert not _accepted_by_jsonschema(schema, payload)
    assert not _accepted_by_pydantic(JobMessage, payload)


@pytest.mark.parametrize(
    "drop",
    ["output_images", "model_version", "processing_seconds"],
)
def test_completed_missing_required_field_rejected_by_both(
    valid_completed, drop
) -> None:
    schema = load_schema("completion")
    payload = {k: v for k, v in valid_completed.items() if k != drop}
    assert not _accepted_by_jsonschema(schema, payload)
    assert not _accepted_by_pydantic(CompletionMessage, payload)


def test_failed_missing_failure_reason_rejected_by_both(valid_failed) -> None:
    schema = load_schema("completion")
    payload = {k: v for k, v in valid_failed.items() if k != "failure_reason"}
    assert not _accepted_by_jsonschema(schema, payload)
    assert not _accepted_by_pydantic(CompletionMessage, payload)


@pytest.mark.parametrize(
    "drop",
    [
        "output_images",
        "model_version",
        "processing_seconds",
        "panel_index",
        "total_panels",
    ],
)
def test_panel_completed_missing_required_field_rejected_by_both(
    valid_panel_completed, drop
) -> None:
    schema = load_schema("completion")
    payload = {k: v for k, v in valid_panel_completed.items() if k != drop}
    assert not _accepted_by_jsonschema(schema, payload)
    assert not _accepted_by_pydantic(CompletionMessage, payload)


def test_completion_unknown_status_rejected_by_both(valid_completed) -> None:
    schema = load_schema("completion")
    payload = valid_completed | {"status": "weird"}
    assert not _accepted_by_jsonschema(schema, payload)
    assert not _accepted_by_pydantic(CompletionMessage, payload)
