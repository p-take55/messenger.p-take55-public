---
name: draft-reply
description: >
  返信が必要な provider message に対して、関連文脈とリスクを踏まえた返信案を作り、aachat asks document にする。
metadata:
  aachat.headline.ja: "返信案の作成"
  aachat.headline.en: "Draft replies"
  aachat.description.ja: "文脈とリスクを踏まえた返信案を作り、aachatで人間の承認を求めます。"
  aachat.description.en: "Prepare context-aware reply options for human approval in aachat."
  aachat.discovery.listed: "false"
---

# draft-reply

返信候補に対して、送信前提の自然な返信案を作る。外部 provider へ送信してはいけない。

## 前提

- 返信要否判定が済んでいなければ、先に `check-inbox` を使う。
- provider token や secret 値を出力しない。
- 根拠がない内容を断定しない。
- 高リスク情報が不足している場合は、返信案より確認質問を優先する。

## 手順

1. 媒体を確認する。Slack、Chatwork、Gmail で文体とフォーマットを変える。
2. provider context と過去の接続ユーザー発言を読む。
3. 使ってよい根拠と確認が必要な情報を分ける。
4. 金額、納期、契約、返金、謝罪、採用、法務、個人情報、機密情報のリスクを確認する。
5. 返信案を 3 種類作る。固定の「標準、短め、丁寧」にはしない。
6. aachat docs の `asks` document を作る。
7. project timeline には返信案本文を直書きせず、WikiLink だけを投稿する。

## asks document に含めるもの

- reply_request_id
- provider
- 原文
- 文脈判定
- 返信要否理由
- 使った根拠
- リスク
- 3 つの返信案
- 採用 / 編集 / 不要として閉じる選択肢

## 媒体別注意

Slack は短く、要点から書く。

Chatwork は必要に応じて To / reply 記法を前提にする。

Gmail は件名、宛名、本文、結び、署名を分ける。CC、BCC、添付、HTML multipart が不明なら不足情報にする。
