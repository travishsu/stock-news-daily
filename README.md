# Market Digest

用 Claude Code + yt-dlp 每日抓取 YouTube 財經頻道字幕，自動分析市場重點。

## 安裝

```bash
# 安裝 yt-dlp（抓字幕用）
pip install yt-dlp

# 或用 brew
brew install yt-dlp
```

## 專案結構

```
market-digest/
├── CLAUDE.md              # Claude Code 讀取的指令檔
├── README.md
├── scripts/
│   ├── channels.txt       # 頻道清單（新增/移除頻道改這裡）
│   └── fetch.sh           # 字幕抓取腳本
├── subtitles/             # 抓下來的字幕檔（gitignore）
└── reports/               # 產出的 Markdown 日報
    └── 2026-03-21.md
```

## 使用方式

在 Claude Code 中打開此專案，然後說：

> 看有沒有最新一集

Claude Code 會自動執行 fetch → 讀取字幕 → 分析 → 產出日報。

## 瀏覽日報 / 週報（Web Viewer）

`web/` 底下有一個零依賴的靜態檢視頁，用 Editorial Terminal 風格呈現所有 `reports/` 下的日報與週報。

```bash
# 1. 產生清單（每次新增日報後重跑一次即可）
uv run python scripts/build_web.py

# 2. 從專案根目錄啟動靜態伺服器
python3 -m http.server 8000

# 3. 瀏覽器打開
open http://localhost:8000/web/
```

網址支援 hash 深連結，例如 `http://localhost:8000/web/#daily/2026-04-10` 或 `#weekly/2026-03-30_2026-04-05`，可直接分享特定一期。

## 自訂頻道

編輯 `scripts/channels.txt`，每行一個 YouTube handle：

```
@kukantieh    # 股乾爹
@SomeNewChannel  # 新頻道
```

## 注意

- 需要網路連線才能抓字幕
- 英文頻道（CNBC/Bloomberg/Yahoo）每日上傳大量短片段，fetch.sh 只抓最新一支
- 如果需要篩選特定關鍵字的影片（如 "market recap"），需修改 fetch.sh 加入 --match-title 參數
