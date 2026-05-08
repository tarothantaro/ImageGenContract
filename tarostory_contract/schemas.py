"""Loaders for the language-neutral JSON Schemas shipped with this package.

Use ``load_schema("job")`` or ``load_schema("completion")`` if you want to
validate raw JSON with ``jsonschema`` (e.g. before constructing a Pydantic
model, or in another language's binding regenerated from the same source).
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Literal

SchemaName = Literal["job", "completion"]


def load_schema(name: SchemaName) -> dict[str, Any]:
    text = resources.files("tarostory_contract").joinpath(
        f"schemas/{name}.json"
    ).read_text(encoding="utf-8")
    return json.loads(text)
