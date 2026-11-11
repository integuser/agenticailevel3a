#!/bin/bash
# Auto-format all Python code with black.
cd "$(dirname "$0")/.." || exit 1
uv run black backend main.py
