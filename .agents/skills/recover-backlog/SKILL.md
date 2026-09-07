---
name: recover-backlog
description: >
  久々に起動したとき、ローカルランナー停止期間、backlog、stuck state、backfill 要否を確認して復旧する。
metadata:
  aachat.headline.ja: "未処理状態の復旧"
  aachat.headline.en: "Recover message backlog"
  aachat.description.ja: "停止期間の未処理状態を整理し、必要な復旧とbackfill範囲を確認します。"
  aachat.description.en: "Review pending and stale states and establish the scope of recovery and backfill."
  aachat.discovery.listed: "false"
---

# recover-backlog

久々起動時や、ローカルランナーが止まっていた可能性があるときに使う。

## 手順

1. `reply-drafter status --json` または runner status payload を確認する。
2. SQLite に残っている state を分類する。
   - received
   - draft_session_requested
   - draft_session_running
   - waiting_for_human
   - approved
   - send_queued
   - send_error
3. `draft_session_running` が古い場合は stale とみなし、再実行候補にする。
4. `waiting_for_human` は asks document と突き合わせる。
5. `approved` / `send_queued` は送信済みでないか確認してから send-approved 対象にする。
6. provider cursor が古い場合は、backfill 範囲を人間に確認する。

## Backfill

backfill は勝手に大規模実行しない。provider、期間、対象 channel / room / query、最大件数を人間に確認する。

Gmail は query、Slack は DM / allowlist channel history、Chatwork は設定 room polling を使う。

## 出力

- 未処理件数
- stale session 件数
- waiting_for_human 件数
- approved but unsent 件数
- send_error 件数
- backfill が必要な provider と推奨範囲
