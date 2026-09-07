---
name: first-run-setup
description: >
  messenger の初回起動時に、ローカルランナー、SQLite、provider connector、credential storage、backfill 要否を確認する。
metadata:
  aachat.headline.ja: "初回セットアップ"
  aachat.headline.en: "First-run setup"
  aachat.description.ja: "ローカルランナーと保存先、接続状態を確認し、初回設定を案内します。"
  aachat.description.en: "Check the local runner, persistent storage, and connectors for initial setup."
  aachat.discovery.listed: "false"
---

# first-run-setup

初回起動時に使う。目的は、ローカルランナーが動ける状態かを確認し、不足があれば人間に次の操作を示すこと。

## 手順

1. `reply-drafter status --json` を試す。CLI が見つからない場合は、インストールが必要だと伝える。
2. SQLite が session workspace 外の永続 data directory にあるか確認する。
3. connector health を見る。Slack、Gmail、Chatwork の状態を `connected`、`needs_attention`、`disabled` で整理する。
4. credential 値は表示しない。secret が必要な場合も、入力先や保存先だけを案内する。
5. provider cursor が無い場合、初回 backfill の範囲を人間に確認する。

## 出力

- ローカルランナーが使えるか
- SQLite が正しい場所にあるか
- provider connector の状態
- 次に人間が実行するコマンド
- backfill をするかどうかの確認事項
