#!/bin/sh
set -e

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

UV="$HOME/.local/bin/uv"

if [ -x "$UV" ]; then
    exec "$UV" run -m sq64
else
    exec uv run -m sq64
fi