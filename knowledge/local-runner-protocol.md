# Local Runner Protocol

ローカルランナーは、各ローカルマシンにインストールされる `reply-drafter` CLI / service である。

## Command surface

```bash
reply-drafter init
reply-drafter start
reply-drafter stop
reply-drafter status --json
reply-drafter doctor --json
reply-drafter catch-up --provider slack --channel-limit 1 --per-channel 1 --json
reply-drafter process --json
reply-drafter send-approved --json
```

agent は任意コマンドを推測実行しない。使うのは上記の安定 surface を基本にする。

この repo には最小の CLI stub が含まれる。`status --json` は未初期化でも JSON を返し、`init --json` は永続 data directory と SQLite schema を作成する。Slackの限定的なbackfill（raw event / queue JSON保存）も実装されている。SQLite取り込み、session起動、background service、実送信、およびGmail / Chatwork Adapterは後続実装である。

## Expected JSON concepts

`status --json` は少なくとも次を返す。

```json
{
  "ok": true,
  "runner": {"running": true},
  "sqlite": {"path": "...", "ok": true},
  "connectors": {
    "slack": {"state": "connected"},
    "gmail": {"state": "needs_attention"},
    "chatwork": {"state": "disabled"}
  },
  "queues": {
    "received": 0,
    "draft_session_requested": 2,
    "waiting_for_human": 1,
    "send_error": 0
  }
}
```

`process --json` は未処理 message の triage 対象を返すか、agent session 起動用 payload を返す。

`send-approved --json` は asks 回答済み decision を読み、provider send result を返す。

## Data directory

SQLite は session workspace に置かない。macOS では `~/Library/Application Support/aachat/reply-drafter/`、Linux では `~/.local/share/aachat/reply-drafter/` のような永続 data directory に置く。

## Security

token、secret、API key は SQLite に保存しない。runner は OS keychain、env provider、または権限付き config file から credential を読む。agent は secret 値を要求しない。
