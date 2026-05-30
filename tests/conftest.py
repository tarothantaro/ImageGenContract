from __future__ import annotations

import pytest


@pytest.fixture
def valid_job() -> dict[str, object]:
    return {
        "schema_version": 1,
        "story_id": "01HX_story",
        "user_id": "uid_abc",
        "request_id": "req_xyz",
        "template_id": "tpl_v1",
        "configurable_options": {"style": "warm"},
        "input_photos": [
            {
                "photo_id": "ph_1",
                "position": 0,
                "gcs_uri": "gs://tarostory-prod-uploads/uid_abc/photos/ph_1.jpg",
            }
        ],
        "output_count": 4,
        "output_prefix": "gs://tarostory-prod-outputs/uid_abc/01HX_story/outputs/",
        "callback_topic": "projects/tarostory-prod/topics/job-completed",
        "enqueued_at": "2026-05-05T12:34:56Z",
    }


@pytest.fixture
def valid_completed() -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_id": "evt_1",
        "story_id": "01HX_story",
        "user_id": "uid_abc",
        "request_id": "req_xyz",
        "status": "completed",
        "output_images": [
            {
                "index": 0,
                "gcs_uri": "gs://b/uid_abc/01HX_story/outputs/0.png",
                "width": 1024,
                "height": 1024,
                "bytes": 873421,
            }
        ],
        "model_version": "tarostory-img-2026-04",
        "processing_seconds": 27.4,
        "completed_at": "2026-05-05T12:35:24Z",
    }


@pytest.fixture
def valid_panel_completed() -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_id": "evt_3",
        "story_id": "01HX_story",
        "user_id": "uid_abc",
        "request_id": "req_xyz",
        "status": "panel_completed",
        "output_images": [
            {
                "index": 1,
                "gcs_uri": "gs://b/uid_abc/01HX_story/outputs/1.png",
                "width": 1024,
                "height": 1024,
                "bytes": 873421,
            }
        ],
        "model_version": "tarostory-img-2026-04",
        "processing_seconds": 12.1,
        "completed_at": "2026-05-05T12:35:10Z",
        "panel_index": 1,
        "total_panels": 4,
    }


@pytest.fixture
def valid_failed() -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_id": "evt_2",
        "story_id": "01HX_story",
        "user_id": "uid_abc",
        "request_id": "req_xyz",
        "status": "failed",
        "completed_at": "2026-05-05T12:35:24Z",
        "failure_reason": "unsupported_template",
    }
