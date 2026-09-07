# Architecture

`messenger` は、aachat 上だけで完結する agent ではなく、aachat とローカル実行基盤が協調する workflow として動く。

## 登場人物

- aachat
- aachat上のエージェント
- ローカルランナー
- ローカルSQLite

実装上は、ローカルランナーの中に Provider Adapter 層を持つ。Slack、Gmail、Chatwork の SDK や公式 API はこの層に閉じ込める。

## Flow

```text
Provider
  -> Provider SDK Adapter
  -> Local Runner
  -> Local SQLite
  -> messenger agent session
  -> aachat Docs / Asks
  -> Human Decision
  -> Local Runner
  -> Provider
```

## 境界

- aachat は provider SDK を知らない。
- aachat上のエージェントは provider SDK を直接使わない。
- ローカルランナーは provider SDK を使うが、返信判断を勝手に確定しない。
- Provider Adapter は provider 差分を吸収し、normalized event と provider send result を返す。
- SQLite は workflow state を持つが、secret store ではない。
- Human の承認は aachat asks に残す。

## No frontend in MVP

MVP ではローカル frontend を置かない。人間との interaction は aachat chat / docs / asks に寄せる。ローカル操作は installable CLI の安定 surface に寄せる。
