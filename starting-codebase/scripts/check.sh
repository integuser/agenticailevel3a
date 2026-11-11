#!/bin/bash
# Run quality checks: formatting (no changes) and tests.
cd "$(dirname "$0")/.." || exit 1
set -e
echo "==> Checking formatting (black)"
uv run black --check backend main.py
echo "==> Running tests (pytest)"
cd backend && uv run pytest
echo "All quality checks passed."
