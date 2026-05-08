"""Behavioural tests for the Pydantic bindings.

Lifted verbatim from the duplicated copies that previously lived in both
ImageGenWorker (tests/unit/test_schema.py) and Application server
(server/tests/unit/test_job_messages.py). This is now the single home.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from tarostory_contract import (
    CURRENT_SCHEMA_VERSION,
    CompletionMessage,
    JobInputPhoto,
    JobMessage,
    OutputImage,
)


# --- JobMessage ---------------------------------------------------------------


def test_job_message_round_trips_canonical_payload(valid_job) -> None:
    job = JobMessage.model_validate(valid_job)

    assert job.schema_version == CURRENT_SCHEMA_VERSION
    assert job.story_id == "01HX_story"
    assert job.input_photos[0].photo_id == "ph_1"
    assert isinstance(job.enqueued_at, datetime)


def test_job_message_rejects_unknown_schema_version(valid_job) -> None:
    with pytest.raises(ValidationError):
        JobMessage.model_validate(valid_job | {"schema_version": 99})


def test_job_message_rejects_extra_fields(valid_job) -> None:
    with pytest.raises(ValidationError):
        JobMessage.model_validate(valid_job | {"surprise": "extra"})


def test_job_message_rejects_missing_required_fields(valid_job) -> None:
    del valid_job["template_id"]
    with pytest.raises(ValidationError):
        JobMessage.model_validate(valid_job)


def test_job_message_rejects_zero_input_photos(valid_job) -> None:
    with pytest.raises(ValidationError):
        JobMessage.model_validate(valid_job | {"input_photos": []})


def test_job_message_rejects_more_than_ten_input_photos(valid_job) -> None:
    photo = valid_job["input_photos"][0]  # type: ignore[index]
    photos = [{**photo, "photo_id": f"ph_{i}", "position": i} for i in range(11)]  # type: ignore[dict-item]
    with pytest.raises(ValidationError):
        JobMessage.model_validate(valid_job | {"input_photos": photos})


def test_job_message_rejects_output_count_out_of_range(valid_job) -> None:
    with pytest.raises(ValidationError):
        JobMessage.model_validate(valid_job | {"output_count": 0})
    with pytest.raises(ValidationError):
        JobMessage.model_validate(valid_job | {"output_count": 17})


def test_job_message_rejects_negative_position(valid_job) -> None:
    valid_job["input_photos"] = [{**valid_job["input_photos"][0], "position": -1}]  # type: ignore[index]
    with pytest.raises(ValidationError):
        JobMessage.model_validate(valid_job)


def test_job_message_rejects_non_gs_input_uri(valid_job) -> None:
    valid_job["input_photos"] = [
        {**valid_job["input_photos"][0], "gcs_uri": "https://example.com/x"}  # type: ignore[index]
    ]
    with pytest.raises(ValidationError, match="gcs_uri"):
        JobMessage.model_validate(valid_job)


def test_job_message_rejects_input_uri_without_object_part(valid_job) -> None:
    valid_job["input_photos"] = [
        {**valid_job["input_photos"][0], "gcs_uri": "gs://only-bucket"}  # type: ignore[index]
    ]
    with pytest.raises(ValidationError, match="gcs_uri"):
        JobMessage.model_validate(valid_job)


def test_job_message_rejects_output_prefix_without_trailing_slash(valid_job) -> None:
    with pytest.raises(ValidationError, match="output_prefix"):
        JobMessage.model_validate(valid_job | {"output_prefix": "gs://b/path/no-slash"})


def test_job_message_rejects_output_prefix_not_in_gcs_form(valid_job) -> None:
    with pytest.raises(ValidationError, match="output_prefix"):
        JobMessage.model_validate(valid_job | {"output_prefix": "/local/path/"})


def test_job_message_rejects_callback_topic_not_in_canonical_form(valid_job) -> None:
    with pytest.raises(ValidationError, match="callback_topic"):
        JobMessage.model_validate(valid_job | {"callback_topic": "topic-name"})


def test_job_input_photo_can_be_constructed_directly() -> None:
    photo = JobInputPhoto(photo_id="ph_1", position=0, gcs_uri="gs://b/o.jpg")
    assert photo.photo_id == "ph_1"


def test_job_message_is_frozen(valid_job) -> None:
    job = JobMessage.model_validate(valid_job)
    with pytest.raises(ValidationError):
        job.story_id = "different"  # type: ignore[misc]


# --- CompletionMessage --------------------------------------------------------


def test_completion_message_completed_round_trips(valid_completed) -> None:
    msg = CompletionMessage.model_validate(valid_completed)

    assert msg.status == "completed"
    assert msg.output_images is not None
    assert msg.output_images[0].gcs_uri.endswith("/0.png")
    assert msg.failure_reason is None


def test_completion_message_failed_round_trips(valid_failed) -> None:
    msg = CompletionMessage.model_validate(valid_failed)

    assert msg.status == "failed"
    assert msg.failure_reason == "unsupported_template"
    assert msg.output_images is None


def test_completion_message_completed_requires_output_images(valid_completed) -> None:
    del valid_completed["output_images"]
    with pytest.raises(ValidationError, match="output_images"):
        CompletionMessage.model_validate(valid_completed)


def test_completion_message_completed_requires_model_version(valid_completed) -> None:
    del valid_completed["model_version"]
    with pytest.raises(ValidationError, match="model_version"):
        CompletionMessage.model_validate(valid_completed)


def test_completion_message_completed_requires_processing_seconds(valid_completed) -> None:
    del valid_completed["processing_seconds"]
    with pytest.raises(ValidationError, match="processing_seconds"):
        CompletionMessage.model_validate(valid_completed)


def test_completion_message_completed_rejects_failure_reason(valid_completed) -> None:
    with pytest.raises(ValidationError, match="failure_reason"):
        CompletionMessage.model_validate(
            valid_completed | {"failure_reason": "should not be here"}
        )


def test_completion_message_failed_requires_failure_reason(valid_failed) -> None:
    del valid_failed["failure_reason"]
    with pytest.raises(ValidationError, match="failure_reason"):
        CompletionMessage.model_validate(valid_failed)


def test_completion_message_failed_rejects_output_images(valid_failed) -> None:
    bad = valid_failed | {
        "output_images": [
            {"index": 0, "gcs_uri": "gs://b/x.png", "width": 1, "height": 1, "bytes": 1}
        ]
    }
    with pytest.raises(ValidationError, match="output_images"):
        CompletionMessage.model_validate(bad)


def test_completion_message_rejects_unknown_status(valid_completed) -> None:
    with pytest.raises(ValidationError):
        CompletionMessage.model_validate(valid_completed | {"status": "weird"})


def test_completion_message_rejects_extra_fields(valid_completed) -> None:
    with pytest.raises(ValidationError):
        CompletionMessage.model_validate(valid_completed | {"hidden": True})


def test_output_image_rejects_non_gs_uri() -> None:
    with pytest.raises(ValidationError, match="gcs_uri"):
        OutputImage(index=0, gcs_uri="http://x", width=1, height=1, bytes=1)


def test_output_image_rejects_uri_without_object() -> None:
    with pytest.raises(ValidationError, match="gcs_uri"):
        OutputImage(index=0, gcs_uri="gs://only-bucket", width=1, height=1, bytes=1)


def test_completion_message_completed_at_is_timezone_aware(valid_completed) -> None:
    msg = CompletionMessage.model_validate(valid_completed)
    assert msg.completed_at.tzinfo is not None
    assert msg.completed_at.astimezone(timezone.utc).year == 2026
