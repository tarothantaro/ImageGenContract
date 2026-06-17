# Image Gen Contract

Wire-format contract for the two Pub/Sub messages that flow between the
TaroStory API server (`../Application/server`) and the image-gen worker
(`../ImageGenWorker`):

| Topic               | Direction              | Schema                                    |
| ------------------- | ---------------------- | ----------------------------------------- |
| `image-gen-jobs`    | API → worker           | `image_gen_contract/schemas/job.json`        |
| `job-completed`     | worker → API           | `image_gen_contract/schemas/completion.json` |

Both repos consume this package; **structural drift between worker and API
server is the class of bug this repo exists to make impossible.**

The **job** message is intentionally a thin selector — `{schema_version,
story_id, user_id, request_id, type, id, input_images[]}`. It names *what* to
generate (prompt `type`/`id` → `prompts/<type>_<id>.json`, rendered through the
single `templates/1`) but carries **no image bytes and no `gcs_uri`**: the
worker downloads each input from object storage by the deterministic name
`<user_id>_<story_id>_input_<position>.png`. Output location and completion
topic are worker config, not per-message.

## Layout

```
image_gen_contract/
  __init__.py        # re-exports
  messages.py        # Pydantic v2 bindings (the Python binding both repos use)
  schemas.py         # load_schema("job"|"completion") for raw-JSON consumers
  schemas/           # canonical, language-neutral JSON Schemas (Draft 2020-12)
    job.json
    completion.json
tests/
  test_messages.py             # behavioural tests for the Pydantic models
  test_jsonschema_alignment.py # parity check: pydantic ↔ jsonschema agree
```

## Use from Python

```python
from image_gen_contract import (
    CURRENT_SCHEMA_VERSION,
    JobMessage,
    JobInputImage,
    CompletionMessage,
    OutputImage,
    load_schema,
)

job = JobMessage.model_validate(payload)            # full validation
schema = load_schema("job")                          # raw JSON Schema dict
```

## Use from another language

The JSON Schemas in `image_gen_contract/schemas/` are Draft 2020-12 and are
the language-neutral source of truth. To generate bindings in another
language without re-implementing them by hand:

* **Dart / TypeScript / Go / etc.** — `quicktype` (https://quicktype.io)
  produces idiomatic models directly from JSON Schema for a wide set of
  languages.
* **Python (regenerate)** — `datamodel-code-generator` (`datamodel-codegen`)
  produces Pydantic v2 from JSON Schema. We do **not** use it here because
  the contract carries cross-field business rules (`if/then` between
  `status` and the field set) and tuned `ValueError` messages that round-trip
  imperfectly through codegen; the hand-written `messages.py` is the binding,
  and `test_jsonschema_alignment.py` keeps it in sync with the JSON.

## Local installation

Both consumer repos pin this package by name. Install once into the shared
venv with an editable install so edits show up immediately in both consumers:

```bash
~/python_env/torch-env/bin/pip install -e /path/to/ImageGenContract
```

Each consumer's `run_tests.sh` runs the same install line idempotently before
its test suite.

## Tests

```bash
./run_tests.sh
```

Runs the behavioural Pydantic tests plus `test_jsonschema_alignment.py`,
which fails if any fixture is accepted by Pydantic but rejected by the JSON
Schema (or vice versa).
