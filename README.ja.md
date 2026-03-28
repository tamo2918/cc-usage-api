# CC Usage API

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) のセッション使用量データ（レートリミット、コスト、コンテキストウィンドウ）をローカルREST APIとして公開するツールです。

Claude Code の [statusline機能](https://code.claude.com/docs/en/statusline.md) を利用しています。statuslineスクリプトがセッションデータをファイルに保存し、軽量なFastAPIサーバーがそれをAPIとして他のアプリケーションから取得できるようにします。

**[English README](./README.md)**

## アーキテクチャ

```
Claude Code  ──stdin JSON──▶  statusline_writer.py  ──file──▶  ~/.claude/usage_data/current.json
                                                                         │
                                                                    server.py (FastAPI)
                                                                         │
                                                          REST API / SSE / Dashboard
```

## セットアップ

```bash
git clone https://github.com/tamo2918/cc-usage-api.git
cd cc-usage-api
./setup.sh
```

セットアップスクリプトが以下を自動で行います:
1. `~/.claude/usage_data/` ディレクトリの作成
2. Python仮想環境の作成と依存関係のインストール
3. `~/.claude/settings.json` へのstatusLine設定
4. `start.sh` 起動スクリプトの生成

その後、Claude Codeを再起動してAPIサーバーを起動:

```bash
./start.sh
```

## APIエンドポイント

| エンドポイント | 説明 |
|---|---|
| `GET /` | API情報と利用可能なエンドポイント一覧 |
| `GET /usage` | 全使用量データ（最新スナップショット） |
| `GET /rate-limits` | レートリミット（リセットまでの残り時間付き） |
| `GET /cost` | セッションコストと所要時間 |
| `GET /context` | コンテキストウィンドウ使用率 |
| `GET /model` | 使用中のモデル情報 |
| `GET /history` | 履歴スナップショット（`?limit=N&session_id=X`） |
| `GET /history/summary` | 使用量の集約サマリー |
| `GET /stream` | Server-Sent Events（リアルタイム更新） |
| `GET /dashboard` | ブラウザ用Webダッシュボード |
| `GET /health` | ヘルスチェック |
| `GET /docs` | Swagger UI（自動生成APIドキュメント） |

## レスポンス例

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

## リアルタイム更新 (SSE)

`/stream` エンドポイントでServer-Sent Eventsに接続:

```javascript
const evtSource = new EventSource('http://localhost:8390/stream');
evtSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('レートリミット (5h):', data.rate_limits?.five_hour?.used_percentage);
};
```

## 活用例

### Raycastスクリプトコマンド

```bash
#!/bin/bash
# @raycast.title CC Usage
# @raycast.mode inline
curl -s http://localhost:8390/rate-limits | jq -r '"5h: \(.rate_limits.five_hour.used_percentage)% | 7d: \(.rate_limits.seven_day.used_percentage)%"'
```

### macOSメニューバー（BitBar/xbar）

```bash
#!/bin/bash
data=$(curl -s http://localhost:8390/rate-limits 2>/dev/null)
five=$(echo "$data" | jq -r '.rate_limits.five_hour.used_percentage // "?"')
echo "Claude: ${five}%"
```

### シェルエイリアス

```bash
alias cc-usage='curl -s http://localhost:8390/rate-limits | jq .'
```

## 設定

| 環境変数 | デフォルト | 説明 |
|---|---|---|
| `CC_USAGE_API_HOST` | `127.0.0.1` | バインドアドレス |
| `CC_USAGE_API_PORT` | `8390` | ポート番号 |

## セキュリティ

- サーバーはデフォルトで `127.0.0.1` にバインド（ローカルホストのみ）
- ローカルファイルパス等の機密フィールド（`cwd`, `workspace`, `transcript_path`）はAPIレスポンスから除去済み。`?raw=true` でローカルデバッグ用に取得可能
- CORSは `allow_credentials=False`、GETメソッドのみ許可
- レートリミットデータはClaude Pro/Maxサブスクリプションのみ

## 必要要件

- Python 3.10+
- Claude Code v2.1.80+（statusline機能対応版）
- Claude Pro または Max サブスクリプション（レートリミットデータの取得に必要）

## ライセンス

[MIT](./LICENSE)
