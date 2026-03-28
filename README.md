# CC Usage API

Expose your [Claude Code](https://docs.anthropic.com/en/docs/claude-code) session usage data (rate limits, cost, context window) as a local REST API.

Built on top of Claude Code's [statusline feature](https://code.claude.com/docs/en/statusline.md) — the statusline script saves session data to a file, and a lightweight FastAPI server makes it available as an API for other applications to consume.

**[Japanese README / 日本語README](./README.ja.md)**

## Architecture

```
Claude Code  ──stdin JSON──▶  statusline_writer.py  ──file──▶  ~/.claude/usage_data/current.json
                                                                         │
                                                                    server.py (FastAPI)
                                                                         │
                                                          REST API / SSE / Dashboard
```

## Quick Start

```bash
git clone https://github.com/tamo2918/cc-usage-api.git
cd cc-usage-api
./setup.sh
```

The setup script will:
1. Create `~/.claude/usage_data/` directory
2. Create a Python virtual environment and install dependencies
3. Configure Claude Code's `statusLine` in `~/.claude/settings.json`
4. Generate a `start.sh` convenience script

Then restart Claude Code and start the API server:

```bash
./start.sh
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | API info and available endpoints |
| `GET /usage` | Full usage data (latest snapshot) |
| `GET /rate-limits` | Rate limits with human-readable reset times |
| `GET /cost` | Session cost and duration |
| `GET /context` | Context window usage |
| `GET /model` | Current model info |
| `GET /history` | Historical snapshots (`?limit=N&session_id=X`) |
| `GET /history/summary` | Aggregated usage summary |
| `GET /stream` | Server-Sent Events for real-time updates |
| `GET /dashboard` | Built-in web dashboard |
| `GET /health` | Health check |
| `GET /docs` | Interactive Swagger UI (auto-generated) |

## Example Responses

### `GET /rate-limits`

```json
{
  "rate_limits": {
    "five_hour": {
      "used_percentage": 35.2,
      "resets_at": 1774677005
    },
    "seven_day": {
      "used_percentage": 12.8,
      "resets_at": 1774929005
    }
  },
  "five_hour_resets_in": "1h 59m 50s",
  "seven_day_resets_in": "71h 59m 50s"
}
```

### `GET /cost`

```json
{
  "cost": {
    "total_cost_usd": 0.1234,
    "total_duration_ms": 120000,
    "total_api_duration_ms": 45000,
    "total_lines_added": 50,
    "total_lines_removed": 10
  },
  "session_duration_human": "2m 0s"
}
```

## Real-Time Updates (SSE)

Connect to `/stream` for Server-Sent Events:

```javascript
const evtSource = new EventSource('http://localhost:8390/stream');
evtSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Rate limit (5h):', data.rate_limits?.five_hour?.used_percentage);
};
```

## Integration Examples

### Raycast Script Command

```bash
#!/bin/bash
# @raycast.title CC Usage
# @raycast.mode inline
curl -s http://localhost:8390/rate-limits | jq -r '"5h: \(.rate_limits.five_hour.used_percentage)% | 7d: \(.rate_limits.seven_day.used_percentage)%"'
```

### macOS Menu Bar (via BitBar/xbar)

```bash
#!/bin/bash
data=$(curl -s http://localhost:8390/rate-limits 2>/dev/null)
five=$(echo "$data" | jq -r '.rate_limits.five_hour.used_percentage // "?"')
echo "Claude: ${five}%"
```

### Shell Alias

```bash
alias cc-usage='curl -s http://localhost:8390/rate-limits | jq .'
```

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `CC_USAGE_API_HOST` | `127.0.0.1` | Bind address |
| `CC_USAGE_API_PORT` | `8390` | Port number |

## Security

- The server binds to `127.0.0.1` by default (localhost only).
- Sensitive fields (`cwd`, `workspace`, `transcript_path`) are stripped from API responses. Use `?raw=true` to include them for local debugging.
- CORS is configured with `allow_credentials=False` and GET-only methods.
- Rate limit data is only available for Claude Pro/Max subscribers.

## Requirements

- Python 3.10+
- Claude Code v2.1.80+ (with statusline support)
- Claude Pro or Max subscription (for rate limit data)

## License

[MIT](./LICENSE)

## Credits

Inspired by the article: [Claude Code ステータスラインでレートリミットを可視化](https://nyosegawa.com/posts/claude-code-statusline-rate-limits/)
