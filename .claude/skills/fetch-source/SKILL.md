---
name: fetch-source
description: 只抓取字幕（不進行分析），適用於重新抓取特定頻道、補抓失敗的來源、或單獨執行 YouTube / Podcast 抓取步驟。當使用者說「幫我重抓 @xxx」、「只抓字幕」、「補抓今天的 Podcast」、「fetch @xxx」時觸發。注意：完整日報流程（抓取+分析+產出）請用 CLAUDE.md 定義的主流程，不需要觸發本 SKILL。
---

# fetch-source

## 指令對照

| 來源類型 | 指令 |
|----------|------|
| 所有 YouTube 頻道 + 播放清單 | `bash scripts/fetch.sh` |
| 單一 YouTube 頻道 | `bash scripts/fetch.sh @handle` |
| 所有 Podcast | `uv run scripts/fetch_podcast.py` |
| 單一 Podcast | `uv run scripts/fetch_podcast.py @handle` |

## 判斷要用哪個指令

- 使用者提到 YouTube 頻道、`@handle`、播放清單 → `fetch.sh`
- 使用者提到 Podcast、RSS → `fetch_podcast.py`
- 不確定 → 確認來源類型（在 `sources/channels.txt` 還是 `sources/podcasts.txt`？）
- 全部重抓 → 兩個都跑

## 輸出位置

字幕存到 `subtitles/YYYY-MM-DD/`，命名規則：
- `{handle}_{videoId}.{lang}.vtt` — VTT 字幕原檔
- `{handle}_{videoId}.{lang}.txt` — 轉換後純文字（5 分鐘一段落）
- `{handle}_meta.txt` — 元數據（video_id|title|date|channel）

## 常見情境

**情境 1：某頻道昨天沒抓到，今天補抓**
```bash
bash scripts/fetch.sh @kukantieh
```

**情境 2：某 Podcast 轉錄失敗，重新跑**
```bash
uv run scripts/fetch_podcast.py @gooaye
```
注意：已存在的字幕會跳過，若要強制重新抓取需先手動刪除對應 .vtt 和 .txt 檔。

**情境 3：只想更新播放清單內容**
```bash
bash scripts/fetch.sh  # fetch.sh 同時處理 channels.txt 和 playlists.txt
```
