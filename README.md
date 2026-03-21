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
