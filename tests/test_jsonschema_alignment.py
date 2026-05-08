"""Parity check between the JSON Schemas and the Pydantic bindings.

Both layers must agree on what is acceptable. If a payload is accepted by one
and rejected by the other, the contract has drifted between the
language-neutral source of truth (``schemas/*.json``) and the Python binding
(``messages.py``) — a class of bug we cannot afford between worker and API.
"""

from __future__ import annotations

import jsonschema
import pytest
from pydantic import ValidationError

from tarostory_contract import CompletionMessage, JobMessage, load_schema


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
def test_completed_missing_required_field_rejected_by_both(valid_completed, drop) -> None:
    schema = load_schema("completion")
    payload = {k: v for k, v in valid_completed.items() if k != drop}
    assert not _accepted_by_jsonschema(schema, payload)
    assert not _accepted_by_pydantic(CompletionMessage, payload)


def test_failed_missing_failure_reason_rejected_by_both(valid_failed) -> None:
    schema = load_schema("completion")
    payload = {k: v for k, v in valid_failed.items() if k != "failure_reason"}
    assert not _accepted_by_jsonschema(schema, payload)
    assert not _accepted_by_pydantic(CompletionMessage, payload)


def test_completion_unknown_status_rejected_by_both(valid_completed) -> None:
    schema = load_schema("completion")
    payload = valid_completed | {"status": "weird"}
    assert not _accepted_by_jsonschema(schema, payload)
    assert not _accepted_by_pydantic(CompletionMessage, payload)
