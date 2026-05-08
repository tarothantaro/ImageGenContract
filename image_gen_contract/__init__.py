"""Wire-format contract between the Tarostory API server and the image-gen worker.

Both repos import from this package — there is no second Python module that
mirrors these shapes. The JSON Schemas in ``schemas/`` are the language-neutral
source of truth; ``image_gen_contract.messages`` is the Python binding.
"""

from .messages import (
    CURRENT_SCHEMA_VERSION,
    CompletionMessage,
    JobInputPhoto,
    JobMessage,
    OutputImage,
)
from .schemas import load_schema

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "CompletionMessage",
    "JobInputPhoto",
    "JobMessage",
    "OutputImage",
    "load_schema",
]

__version__ = "0.1.0"
