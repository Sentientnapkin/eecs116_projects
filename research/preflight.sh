#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
preflight_python="${PREFLIGHT_PYTHON:-/data/backups/rganapa/Sebastian/venv-teacher/bin/python}"
exec "$preflight_python" "$script_dir/preflight.py" "$@"
