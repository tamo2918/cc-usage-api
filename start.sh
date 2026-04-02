#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${CC_USAGE_API_PORT:-8390}"
echo "Starting CC Usage API on http://localhost:$PORT"
echo "Dashboard: http://localhost:$PORT/dashboard"
echo "API docs:  http://localhost:$PORT/docs"
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/server.py"
