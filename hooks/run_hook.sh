#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
if [ -f "$PLUGIN_ROOT/venv/bin/activate" ]; then
    source "$PLUGIN_ROOT/venv/bin/activate"
elif [ -f "$PLUGIN_ROOT/venv/Scripts/activate" ]; then
    source "$PLUGIN_ROOT/venv/Scripts/activate"
fi
python3 "$SCRIPT_DIR/$1" 2>/dev/null
