# Provider Adapters

Provider Adapter は、Slack、Gmail、Chatwork など provider ごとの SDK / API 差分を吸収する層である。

## 方針

乗れる SDK がある provider は SDK に乗る。目的は、署名検証、OAuth、token refresh、webhook routing、API response parsing の自前実装を減らすこと。

| provider | 方針 |
|---|---|
| Slack | `Bolt for Python` / `slack_sdk` を優先する。ローカル開発や個人運用では Socket Mode が楽。公開 URL を持てる場合は Events API HTTP endpoint も選択肢にする。 |
| Gmail | Google 公式の Python client libraries を使う。最初は polling。Pub/Sub push は後続でよい。 |
| Chatwork | 公式 API / Webhook 仕様に合わせた薄い adapter を作る。公式 Python SDK を前提にしない。HTTP client は `httpx` などを使う。 |
| 共通 HTTP webhook | 必要なら `FastAPI` または `Starlette` を使う。長期運用では Python 標準の `http.server` に寄せすぎない。 |

## Normalized event

Adapter は provider payload を次のような共通形式に変換する。

```yaml
provider: slack | gmail | chatwork
provider_locator:
  workspace_id: ...
  channel_id: ...
  room_id: ...
  thread_id: ...
  message_id: ...
  message_ts: ...
sender:
  id: ...
  display_name: ...
text: ...
received_at: ...
context_locator: ...
idempotency_key: ...
```

## Adapter がやること

- webhook / polling / backfill
- signature verification
- OAuth / token refresh
- provider API call
- provider response parsing
- normalized event creation

## Adapter がやらないこと

- 返信要否の最終判断
- asks document 作成
- 人間承認なしの送信
- workflow state の勝手な terminal 化
- secret 値の shared document 出力
