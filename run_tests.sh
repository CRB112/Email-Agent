#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

if [[ -n "${EMAIL_AGENT_PYTHON:-}" ]]; then
    python_executable="$EMAIL_AGENT_PYTHON"
elif [[ -x "$project_dir/.venv/bin/python" ]]; then
    python_executable="$project_dir/.venv/bin/python"
else
    python_executable="python3"
fi

"$python_executable" -m unittest discover -s tests -v
"$python_executable" -m tests.simulate "$@"
