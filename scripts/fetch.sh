#!/usr/bin/env bash
set -euo pipefail

# 抓取 YouTube 頻道最新影片字幕
# 用法：
#   bash scripts/fetch.sh            # 抓所有頻道
#   bash scripts/fetch.sh @kukantieh # 只抓特定頻道

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CHANNELS_FILE="$SCRIPT_DIR/channels.txt"
SUB_DIR="$PROJECT_DIR/subtitles"

mkdir -p "$SUB_DIR"

# 檢查 yt-dlp 是否安裝
if ! command -v yt-dlp &> /dev/null; then
    echo "ERROR: yt-dlp 未安裝。請執行: pip install yt-dlp" >&2
    exit 1
fi

# 讀取頻道列表，過濾註解和空行
get_channels() {
    grep -v '^\s*#' "$CHANNELS_FILE" | grep -v '^\s*$' | awk '{print $1}'
}

# 抓取單一頻道的最新影片字幕
fetch_channel() {
    local handle="$1"
    local url="https://www.youtube.com/${handle}/videos"

    echo "=== 正在處理: $handle ==="

    # 抓取最新一支影片的字幕（優先手動字幕，退而求其次自動字幕）
    # --playlist-items 1 只抓第一支（最新）
    # --skip-download 不下載影片本身
    # --write-sub 寫入手動字幕
    # --write-auto-sub 寫入自動字幕
    # --sub-lang 優先中文，其次英文
    # --convert-subs vtt 統一格式
    yt-dlp \
        --playlist-items 1 \
        --skip-download \
        --write-sub \
        --write-auto-sub \
        --sub-lang "zh-Hant,zh-Hans,zh,en" \
        --convert-subs vtt \
        --output "$SUB_DIR/${handle}_%(id)s" \
        --no-overwrites \
        --ignore-errors \
        --print-to-file "%(id)s|%(title)s|%(upload_date)s|%(channel)s" "$SUB_DIR/${handle}_meta.txt" \
        "$url" 2>&1 | grep -v "^\[debug\]" || true

    echo ""
}

# 主邏輯
if [ $# -gt 0 ]; then
    # 指定頻道
    fetch_channel "$1"
else
    # 所有頻道
    while IFS= read -r handle; do
        fetch_channel "$handle"
    done < <(get_channels)
fi

echo "=== 完成 ==="
echo "字幕檔案位於: $SUB_DIR/"
ls -la "$SUB_DIR/" 2>/dev/null || echo "(目錄為空)"
