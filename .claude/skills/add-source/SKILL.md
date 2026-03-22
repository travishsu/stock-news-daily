---
name: add-source
description: 新增或移除股市日報的資料來源（YouTube 頻道、Podcast RSS、YouTube 播放清單）。當使用者說「幫我加一個頻道」、「新增這個播客」、「加這個播放清單」、「移除某頻道」，或直接提供 YouTube @handle、RSS URL、播放清單 URL 時觸發。
---

# add-source

## 來源檔案對照

| 類型 | 檔案 | 格式 |
|------|------|------|
| YouTube 頻道 | `sources/channels.txt` | `@handle  # 說明（可選）` |
| Podcast RSS | `sources/podcasts.txt` | `@handle  rss_url  頻道名稱` |
| YouTube 播放清單 | `sources/playlists.txt` | `name  playlist_url` |
| Whisper 提示詞 | `sources/whisper_prompts.txt` | `@handle<TAB>提示詞文字` |

## 新增來源

1. **判斷類型**：
   - YouTube `@handle` 或頻道 ID → `channels.txt`
   - RSS feed URL（soundon.fm、firstory.me 等） → `podcasts.txt`
   - `youtube.com/playlist?list=` URL → `playlists.txt`
   - 若不確定，詢問使用者

2. 讀取對應檔案，確認 handle 尚未存在（避免重複）

3. 寫入：在適當位置附加一行
   - `channels.txt` 有「中文頻道」和「英文頻道」兩個區塊，加在對應區塊末尾
   - `playlists.txt` 的 name 不加 `@`，直接是短識別名（如 `madmoney`）

4. **Podcast 的 Whisper 提示詞**：新增 Podcast 時，詢問是否要加 Whisper 初始提示詞（中文 Podcast 建議加，有助於轉錄準確度）。若要加，同時更新 `sources/whisper_prompts.txt`，格式：`@handle<TAB>提示詞`

5. **驗證（選用）**：詢問使用者是否要立即驗證能否抓取：
   - YouTube 頻道：`bash scripts/fetch.sh @handle`
   - Podcast：`uv run scripts/fetch_podcast.py @handle`

## 移除來源

1. 讀取對應檔案，找到該行
2. 用 Edit 工具精確移除該行
3. 若 `whisper_prompts.txt` 有對應行，一併移除

## 注意事項

- Podcast handle 和 YouTube handle 共用命名空間，避免重複
- 使用者若只提供頻道名稱（非 handle），先詢問確認 `@handle`
