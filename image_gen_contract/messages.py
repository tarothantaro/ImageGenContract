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


class JobInputImage(_StrictModel):
    """Metadata for one input image (DESIGN.md §5.1).

    Carries no image bytes and no ``gcs_uri``: the worker downloads each input
    from object storage by the deterministic per-story name
    ``<user_id>_<story_id>_input_<position>.png``, derived from the enclosing
    job's ``user_id`` / ``story_id`` and this entry's ``position``. ``photo_id``
    is the canonical photo doc id, carried for tracing/correlation only.

    ``age`` is the human-readable age of the person in this photo at story-
    creation time (e.g. ``"2-year-old"`` or ``"23-month-old"``), computed by the
    API server from the user's selected role. The worker substitutes it into the
    prompt set's ``{INPUT_<position+1>_AGE}`` placeholder. Optional: a job
    without it leaves the placeholder dropped (back-compat with age-less jobs).
    """

    photo_id: str = Field(min_length=1)
    position: int = Field(ge=0)
    age: str | None = Field(default=None, max_length=32)


class JobMessage(_StrictModel):
    """Outbound message → image-gen-jobs topic (DESIGN.md §5.1).

    The event names *what* to generate, not the assets themselves: the worker
    loads the prompt set ``prompts/<type>_<id>.json`` and renders it through the
    single render template ``templates/1``, downloading inputs by the
    ``<user_id>_<story_id>_input_<position>.png`` convention. Output location and
    completion topic are worker config, not per-message.
    """

    schema_version: Literal[1]
    story_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    # Prompt selector: ``prompts/<type>_<id>.json`` (e.g. type=1, id=1 → 1_1).
    type: int = Field(ge=1)
    id: int = Field(ge=1)
    input_images: list[JobInputImage] = Field(min_length=1, max_length=10)


class OutputImage(_StrictModel):
    index: int = Field(ge=0)
    gcs_uri: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    bytes: int = Field(ge=1)
    # Storybook layout (DESIGN.md §4). ``index`` stays the flat unique ordinal;
    # these decompose it into which page (panel) the image is and which A/B
    # variant: panel_index = index // variants_per_panel, variant = index %
    # variants_per_panel. Default 0/0 keeps single-variant (legacy) jobs valid.
    panel_index: int = Field(default=0, ge=0)
    variant: int = Field(default=0, ge=0)

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
