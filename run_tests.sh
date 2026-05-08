#!/usr/bin/env bash
set -euo pipefail
PYTHON=~/python_env/torch-env/bin/python
cd "$(dirname "$0")"
exec "$PYTHON" -m pytest tests/ --cov=tarostory_contract --cov-report=term-missing "$@"
