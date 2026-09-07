---
name: check-inbox
description: >
  ローカルランナーから未処理 message のチェック依頼を受けたとき、返信要否を判定し、返信候補だけ draft-reply に進める。
metadata:
  aachat.headline.ja: "未処理メッセージの確認"
  aachat.headline.en: "Inbox triage"
  aachat.description.ja: "未処理メッセージの返信要否を判定し、返信案作成へ引き継ぎます。"
  aachat.description.en: "Triage pending messages and route reply candidates for drafting."
  aachat.discovery.listed: "false"
---

# check-inbox

未処理 message を triage する。返信案生成は `draft-reply` の責務なので、この skill では判定と不足情報の整理に集中する。

## 入力として見るもの

- provider
- provider_locator
- sender
- destination
- text
- context summary
- received_at
- current state

## 判定

返信候補にするもの:

- 自分宛ての DM / mention / To
- 質問、依頼、承認要求、日程調整、資料確認
- 未完了 thread
- 返信待ちの conversation

閉じてよいもの:

- bot 通知
- reaction
- 完了報告だけ
- 全体周知
- すでに別人が回答済み
- 低 signal の雑談

## 出力

```json
{
  "should_reply": true,
  "confidence": 0.82,
  "urgency": "normal",
  "reason": "社外相手から日程確認の質問が来ている",
  "missing_info": ["候補日時"],
  "required_knowledge": ["availability"],
  "close_reason": null
}
```

`confidence` が低い場合は、返信案を作る前に asks または chat で人間確認する。
