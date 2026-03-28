#!/usr/bin/env python3
"""CC Usage API Server

Lightweight HTTP API that serves Claude Code usage data
saved by the statusline_writer.py script.

Endpoints:
  GET /                - API info and available endpoints
  GET /usage           - Full usage data (latest snapshot)
  GET /rate-limits     - Rate limit info (5h & 7d windows)
  GET /cost            - Session cost breakdown
  GET /context         - Context window usage
  GET /model           - Current model info
  GET /history         - Historical usage snapshots
  GET /history/summary - Aggregated usage summary
  GET /health          - Health check

  SSE:
  GET /stream          - Server-Sent Events for real-time updates
"""

import json
import time
import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

DATA_DIR = Path.home() / ".claude" / "usage_data"
DATA_FILE = DATA_DIR / "current.json"
HISTORY_FILE = DATA_DIR / "history.jsonl"


def read_current_data() -> dict | None:
    """Read the latest usage data from the shared file."""
    try:
        if not DATA_FILE.exists():
            return None
        with open(DATA_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def read_history(limit: int = 100, session_id: str | None = None) -> list[dict]:
    """Read historical snapshots from the JSONL file."""
    if not HISTORY_FILE.exists():
        return []
    records = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if session_id and record.get("session_id") != session_id:
                    continue
                records.append(record)
            except json.JSONDecodeError:
                continue
    return records[-limit:]


def compute_summary(records: list[dict]) -> dict:
    """Compute aggregated summary from history records."""
    if not records:
        return {"message": "No history data available"}

    sessions = set()
    latest_rate_limits = None
    total_cost = 0.0

    for r in records:
        sid = r.get("session_id")
        if sid:
            sessions.add(sid)
        cost = (r.get("cost") or {}).get("total_cost_usd")
        if cost is not None:
            total_cost = max(total_cost, cost)
        rl = r.get("rate_limits")
        if rl:
            latest_rate_limits = rl

    return {
        "total_snapshots": len(records),
        "unique_sessions": len(sessions),
        "latest_rate_limits": latest_rate_limits,
        "peak_cost_usd": round(total_cost, 6),
        "first_snapshot": records[0].get("timestamp"),
        "last_snapshot": records[-1].get("timestamp"),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="CC Usage API",
    description="REST API to access Claude Code session usage, rate limits, and cost data.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "CC Usage API",
        "version": "1.0.0",
        "endpoints": {
            "/usage": "Full usage data (latest snapshot)",
            "/rate-limits": "Rate limit info (5h & 7d windows)",
            "/cost": "Session cost breakdown",
            "/context": "Context window usage",
            "/model": "Current model info",
            "/history": "Historical snapshots (query: ?limit=N&session_id=X)",
            "/history/summary": "Aggregated usage summary",
            "/stream": "Server-Sent Events for real-time updates",
            "/health": "Health check",
        },
    }


SENSITIVE_KEYS = {"cwd", "workspace", "transcript_path", "_saved_at", "_saved_at_iso"}


def sanitize_data(data: dict) -> dict:
    """Remove local filesystem paths and internal fields from the response."""
    return {k: v for k, v in data.items() if k not in SENSITIVE_KEYS}


@app.get("/usage")
def get_usage(raw: bool = Query(default=False, description="Include all fields (local use only)")):
    data = read_current_data()
    if data is None:
        return JSONResponse(
            status_code=503,
            content={"error": "No usage data available. Is Claude Code running with the statusline configured?"},
        )
    return data if raw else sanitize_data(data)


@app.get("/rate-limits")
def get_rate_limits():
    data = read_current_data()
    if data is None:
        return JSONResponse(status_code=503, content={"error": "No data available"})

    rate_limits = data.get("rate_limits")
    if rate_limits is None:
        return {
            "message": "Rate limits not available (only present for Pro/Max subscribers after first API response)",
            "rate_limits": None,
        }

    result = {"rate_limits": rate_limits}

    # Add human-readable reset times
    for window in ["five_hour", "seven_day"]:
        w = rate_limits.get(window, {})
        resets_at = w.get("resets_at")
        if resets_at:
            remaining = max(0, resets_at - time.time())
            mins, secs = divmod(int(remaining), 60)
            hours, mins = divmod(mins, 60)
            result[f"{window}_resets_in"] = f"{hours}h {mins}m {secs}s"

    return result


@app.get("/cost")
def get_cost():
    data = read_current_data()
    if data is None:
        return JSONResponse(status_code=503, content={"error": "No data available"})
    cost = data.get("cost", {})
    duration_ms = cost.get("total_duration_ms", 0)
    return {
        "cost": cost,
        "session_duration_human": f"{duration_ms // 60000}m {(duration_ms % 60000) // 1000}s" if duration_ms else None,
    }


@app.get("/context")
def get_context():
    data = read_current_data()
    if data is None:
        return JSONResponse(status_code=503, content={"error": "No data available"})
    return {
        "context_window": data.get("context_window"),
        "exceeds_200k_tokens": data.get("exceeds_200k_tokens"),
    }


@app.get("/model")
def get_model():
    data = read_current_data()
    if data is None:
        return JSONResponse(status_code=503, content={"error": "No data available"})
    return {
        "model": data.get("model"),
        "version": data.get("version"),
    }


@app.get("/history")
def get_history(
    limit: int = Query(default=100, ge=1, le=10000),
    session_id: str | None = Query(default=None),
):
    records = read_history(limit=limit, session_id=session_id)
    return {"count": len(records), "records": records}


@app.get("/history/summary")
def get_history_summary():
    records = read_history(limit=10000)
    return compute_summary(records)


@app.get("/stream")
async def stream_usage():
    """Server-Sent Events endpoint for real-time usage updates."""

    async def event_generator():
        last_saved_at = None
        while True:
            data = read_current_data()
            if data:
                current_saved_at = data.get("_saved_at")
                if current_saved_at != last_saved_at:
                    last_saved_at = current_saved_at
                    yield f"data: {json.dumps(sanitize_data(data), ensure_ascii=False)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
def health():
    data = read_current_data()
    has_data = data is not None
    age = None
    if has_data:
        saved_at = data.get("_saved_at")
        if saved_at:
            age = round(time.time() - saved_at, 1)

    return {
        "status": "ok" if has_data else "waiting",
        "has_data": has_data,
        "data_age_seconds": age,
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Serve the built-in usage dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    if not dashboard_path.exists():
        return HTMLResponse("<h1>dashboard.html not found</h1>", status_code=404)
    return HTMLResponse(dashboard_path.read_text())


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("CC_USAGE_API_HOST", "127.0.0.1")
    port = int(os.environ.get("CC_USAGE_API_PORT", "8390"))
    print(f"Starting CC Usage API on http://{host}:{port}")
    print(f"Dashboard: http://localhost:{port}/dashboard")
    print(f"API docs:  http://localhost:{port}/docs")
    uvicorn.run(app, host=host, port=port)
