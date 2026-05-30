"""Pydantic bindings for the Pub/Sub wire format between the Tarostory API
server and the image-gen worker.

Mirrors ``schemas/job.json`` and ``schemas/completion.json``. The JSON Schemas
are the language-neutral source of truth; this module is the Python binding
both repos consume. ``test_jsonschema_alignment.py`` enforces parity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CURRENT_SCHEMA_VERSION = 1


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class JobInputPhoto(_StrictModel):
    photo_id: str = Field(min_length=1)
    position: int = Field(ge=0)
    gcs_uri: str

    @field_validator("gcs_uri")
    @classmethod
    def _check_gcs_uri(cls, v: str) -> str:
        if not v.startswith("gs://") or "/" not in v[5:]:
            raise ValueError("gcs_uri must be gs://<bucket>/<object>")
        return v


class JobMessage(_StrictModel):
    """Outbound message → image-gen-jobs topic (DESIGN.md §5.1)."""

    schema_version: Literal[1]
    story_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    configurable_options: dict[str, object] = Field(default_factory=dict)
    input_photos: list[JobInputPhoto] = Field(min_length=1, max_length=10)
    output_count: int = Field(ge=1, le=16)
    output_prefix: str
    callback_topic: str
    enqueued_at: datetime

    @field_validator("output_prefix")
    @classmethod
    def _check_output_prefix(cls, v: str) -> str:
        if not v.startswith("gs://") or not v.endswith("/"):
            raise ValueError(
                "output_prefix must be gs://<bucket>/<dir>/ (trailing slash)"
            )
        return v

    @field_validator("callback_topic")
    @classmethod
    def _check_callback_topic(cls, v: str) -> str:
        parts = v.split("/")
        if len(parts) != 4 or parts[0] != "projects" or parts[2] != "topics":
            raise ValueError("callback_topic must be projects/<project>/topics/<name>")
        return v


class OutputImage(_StrictModel):
    index: int = Field(ge=0)
    gcs_uri: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    bytes: int = Field(ge=1)

    @field_validator("gcs_uri")
    @classmethod
    def _check_gcs_uri(cls, v: str) -> str:
        if not v.startswith("gs://") or "/" not in v[5:]:
            raise ValueError("gcs_uri must be gs://<bucket>/<object>")
        return v


class CompletionMessage(_StrictModel):
    """Inbound message ← job-completed topic (DESIGN.md §5.2).

    Three shapes, distinguished by ``status``:

    * ``panel_completed`` — one panel of a multi-panel story finished. Carries
      that single panel's image in ``output_images`` plus ``panel_index`` /
      ``total_panels``. The worker publishes one per panel as it streams a job,
      so the API can surface images to the user as they land. **Not terminal**:
      the result processor records the panel image and notifies the user, but
      does not finalize the story (no credit debit, no status flip).
    * ``completed`` — the whole job finished. Carries every output image. This
      is the terminal success event that finalizes the story.
    * ``failed`` — the job failed terminally; carries ``failure_reason``.
    """

    schema_version: Literal[1]
    event_id: str = Field(min_length=1)
    story_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    status: Literal["completed", "failed", "panel_completed"]
    output_images: list[OutputImage] | None = None
    model_version: str | None = Field(default=None, min_length=1)
    processing_seconds: float | None = Field(default=None, ge=0)
    completed_at: datetime
    failure_reason: str | None = Field(default=None, min_length=1, max_length=64)
    # Set only on ``panel_completed`` (DESIGN.md §5.2): which panel this is and
    # how many the story has in total, so the API can track incremental progress.
    panel_index: int | None = Field(default=None, ge=0)
    total_panels: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _check_status_fields(self) -> "CompletionMessage":
        if self.status in ("completed", "panel_completed"):
            if self.output_images is None:
                raise ValueError(f"output_images required when status={self.status!r}")
            if self.model_version is None:
                raise ValueError(f"model_version required when status={self.status!r}")
            if self.processing_seconds is None:
                raise ValueError(
                    f"processing_seconds required when status={self.status!r}"
                )
            if self.failure_reason is not None:
                raise ValueError(
                    f"failure_reason must be omitted when status={self.status!r}"
                )
            if self.status == "panel_completed":
                if self.panel_index is None:
                    raise ValueError(
                        "panel_index required when status='panel_completed'"
                    )
                if self.total_panels is None:
                    raise ValueError(
                        "total_panels required when status='panel_completed'"
                    )
                if self.panel_index >= self.total_panels:
                    raise ValueError("panel_index must be < total_panels")
        else:  # status == 'failed'
            if self.failure_reason is None:
                raise ValueError("failure_reason required when status='failed'")
            if self.output_images:
                raise ValueError(
                    "output_images must be empty/omitted when status='failed'"
                )
        return self
