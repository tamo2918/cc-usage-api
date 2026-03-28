#!/bin/bash
# Claude Usage API - Setup Script
# Configures the statusline writer and installs dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
DATA_DIR="$CLAUDE_DIR/usage_data"
WRITER_SCRIPT="$SCRIPT_DIR/statusline_writer.py"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== Claude Usage API Setup ==="
echo ""

# 1. Create data directory
echo "[1/5] Creating data directory..."
mkdir -p "$DATA_DIR"
echo "  -> $DATA_DIR"

# 2. Make statusline writer executable
echo "[2/5] Setting permissions..."
chmod +x "$WRITER_SCRIPT"
echo "  -> $WRITER_SCRIPT"

# 3. Create venv and install dependencies
echo "[3/5] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  -> Created venv at $VENV_DIR"
else
    echo "  -> Venv already exists at $VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -q fastapi uvicorn
echo "  -> fastapi, uvicorn installed"

# 4. Configure Claude Code settings
echo "[4/5] Configuring Claude Code statusline..."

if [ -f "$SETTINGS_FILE" ]; then
    # Check if statusLine already exists
    if python3 -c "
import json, sys
with open('$SETTINGS_FILE') as f:
    s = json.load(f)
if 'statusLine' in s:
    print('exists')
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
        echo ""
        echo "  [!] statusLine is already configured in $SETTINGS_FILE"
        echo "  Current config:"
        python3 -c "
import json
with open('$SETTINGS_FILE') as f:
    s = json.load(f)
print(json.dumps(s.get('statusLine', {}), indent=4))
"
        echo ""
        read -p "  Overwrite with new config? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "  -> Skipping statusline config (keeping existing)"
            echo ""
            echo "=== Setup Complete ==="
            echo ""
            echo "To start the API server:"
            echo "  cd $SCRIPT_DIR && $VENV_DIR/bin/python3 server.py"
            echo ""
            echo "API will be available at: http://localhost:8390"
            echo "API docs at: http://localhost:8390/docs"
            exit 0
        fi
    fi

    # Update existing settings
    python3 -c "
import json
with open('$SETTINGS_FILE') as f:
    settings = json.load(f)
settings['statusLine'] = {
    'type': 'command',
    'command': '$WRITER_SCRIPT'
}
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
print('  -> Updated $SETTINGS_FILE')
"
else
    # Create new settings file
    mkdir -p "$CLAUDE_DIR"
    python3 -c "
import json
settings = {
    'statusLine': {
        'type': 'command',
        'command': '$WRITER_SCRIPT'
    }
}
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
print('  -> Created $SETTINGS_FILE')
"
fi

# 5. Create convenience start script
echo "[5/5] Creating start script..."
cat > "$SCRIPT_DIR/start.sh" << 'STARTEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${CLAUDE_USAGE_API_PORT:-8390}"
echo "Starting Claude Usage API on http://localhost:$PORT"
echo "Dashboard: http://localhost:$PORT/dashboard"
echo "API docs:  http://localhost:$PORT/docs"
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/server.py"
STARTEOF
chmod +x "$SCRIPT_DIR/start.sh"
echo "  -> $SCRIPT_DIR/start.sh"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Status line writer: $WRITER_SCRIPT"
echo "Data directory:     $DATA_DIR"
echo ""
echo "To start the API server:"
echo "  $SCRIPT_DIR/start.sh"
echo ""
echo "Or with custom port:"
echo "  CLAUDE_USAGE_API_PORT=9000 $SCRIPT_DIR/start.sh"
echo ""
echo "Endpoints:"
echo "  http://localhost:8390/          - API info"
echo "  http://localhost:8390/usage     - Full usage data"
echo "  http://localhost:8390/rate-limits - Rate limits"
echo "  http://localhost:8390/cost      - Cost info"
echo "  http://localhost:8390/context   - Context window"
echo "  http://localhost:8390/stream    - SSE real-time stream"
echo "  http://localhost:8390/dashboard - Web dashboard"
echo "  http://localhost:8390/docs      - Swagger UI"
echo ""
echo "Note: Restart Claude Code for the statusline change to take effect."
