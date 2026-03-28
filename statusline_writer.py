#!/usr/bin/env python3
"""Claude Code Statusline Script

Reads session JSON from stdin (provided by Claude Code's statusline feature),
saves it to a shared JSON file for the API server, and outputs a formatted
status line for display in Claude Code.
"""

import json
import sys
import os
import time
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None  # Windows

DATA_DIR = Path.home() / ".claude" / "usage_data"
DATA_FILE = DATA_DIR / "current.json"
HISTORY_FILE = DATA_DIR / "history.jsonl"
MAX_HISTORY_LINES = 10000


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_data(data: dict):
    """Atomically write data to the shared JSON file."""
    data["_saved_at"] = time.time()
    data["_saved_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    tmp_file = DATA_FILE.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp_file.rename(DATA_FILE)


def append_history(data: dict):
    """Append a snapshot to the history file (JSONL format) with auto-rotation."""
    record = {
        "timestamp": time.time(),
        "session_id": data.get("session_id"),
        "rate_limits": data.get("rate_limits"),
        "cost": data.get("cost"),
        "context_window": data.get("context_window"),
        "model": data.get("model"),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"

    with open(HISTORY_FILE, "a") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line)
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_UN)

    # Rotate if too large
    try:
        if HISTORY_FILE.stat().st_size > MAX_HISTORY_LINES * 200:  # ~200 bytes per line
            with open(HISTORY_FILE) as f:
                lines = f.readlines()
            if len(lines) > MAX_HISTORY_LINES:
                with open(HISTORY_FILE, "w") as f:
                    f.writelines(lines[-MAX_HISTORY_LINES:])
    except OSError:
        pass


def format_percentage_bar(percentage, width=10):
    """Create a visual bar for percentage values."""
    if percentage is None:
        return "[-?-]"
    filled = int(percentage / 100 * width)
    empty = width - filled
    if percentage < 50:
        color = "\033[32m"  # green
    elif percentage < 80:
        color = "\033[33m"  # yellow
    else:
        color = "\033[31m"  # red
    reset = "\033[0m"
    return f"{color}[{'#' * filled}{'.' * empty}] {percentage:.0f}%{reset}"


def format_statusline(data: dict) -> str:
    """Format data into a human-readable status line for Claude Code."""
    parts = []

    # Model
    model = data.get("model", {})
    model_name = model.get("display_name", model.get("id", "?"))
    parts.append(f"\033[36m{model_name}\033[0m")

    # Rate limits
    rate_limits = data.get("rate_limits")
    if rate_limits:
        five_h = rate_limits.get("five_hour", {})
        seven_d = rate_limits.get("seven_day", {})
        five_pct = five_h.get("used_percentage")
        seven_pct = seven_d.get("used_percentage")

        if five_pct is not None:
            parts.append(f"5h:{format_percentage_bar(five_pct, 8)}")
        if seven_pct is not None:
            parts.append(f"7d:{format_percentage_bar(seven_pct, 8)}")

    # Context window
    ctx = data.get("context_window", {})
    ctx_pct = ctx.get("used_percentage")
    if ctx_pct is not None:
        parts.append(f"ctx:{format_percentage_bar(ctx_pct, 8)}")

    # Cost
    cost = data.get("cost", {})
    total_cost = cost.get("total_cost_usd")
    if total_cost is not None:
        parts.append(f"\033[33m${total_cost:.4f}\033[0m")

    return " | ".join(parts)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, EOFError):
        print("? no data")
        return

    ensure_data_dir()
    save_data(data)
    append_history(data)

    print(format_statusline(data))


if __name__ == "__main__":
    main()
