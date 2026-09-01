#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

if [[ -x "$project_dir/.venv/bin/python" ]]; then
    python_executable="$project_dir/.venv/bin/python"
else
    python_executable="python3"
fi

"$python_executable" -m PyInstaller --noconfirm EmailSiftingAgent.spec

echo
echo "Linux executable created at:"
echo "  $project_dir/dist/EmailSiftingAgent"
