#!/bin/bash
# Fraction of moving windows whose measured direction is right / backwards, per flight (needs ground truth).
cd "$(dirname "$0")" && source "$HOME/.venv/bin/activate"
for f in "$@"; do echo "$(basename "$f"): $(python debug_windows.py "$f" 2>&1 | tail -1)"; done
