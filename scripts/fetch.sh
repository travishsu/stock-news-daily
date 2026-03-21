#!/usr/bin/env bash
set -euo pipefail

# 抓取 YouTube 頻道最新影片字幕
# 用法：
#   bash scripts/fetch.sh            # 抓所有頻道
#   bash scripts/fetch.sh @kukantieh # 只抓特定頻道

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CHANNELS_FILE="$PROJECT_DIR/sources/channels.txt"
PLAYLISTS_FILE="$PROJECT_DIR/sources/playlists.txt"
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

# 讀取播放清單，過濾註解和空行（格式：name URL）
get_playlists() {
    grep -v '^\s*#' "$PLAYLISTS_FILE" | grep -v '^\s*$'
}

# 無字幕時：下載音訊並以 whisper 轉錄
transcribe_fallback() {
    local name="$1"
    local video_id="$2"
    local date_dir="$3"

    local audio_dir="$PROJECT_DIR/audios"
    mkdir -p "$audio_dir"
    local audio_path="$audio_dir/${name}_${video_id}.mp3"
    local vtt_path="$date_dir/${name}_${video_id}.zh.vtt"

    echo "  [whisper] 無字幕，下載音訊進行轉錄..."
    yt-dlp \
        --extract-audio \
        --audio-format mp3 \
        --audio-quality 0 \
        --output "$audio_path" \
        --no-overwrites \
        --ignore-errors \
        "https://www.youtube.com/watch?v=${video_id}" 2>&1 | grep -v "^\[debug\]" || true

    if [ -f "$audio_path" ]; then
        uv run "$SCRIPT_DIR/transcribe.py" "$audio_path" "$vtt_path" --language zh --txt || true
        rm -f "$audio_path"
        echo "  [rm] ${audio_path##*/}"
    else
        echo "  [skip] 音訊下載失敗，略過轉錄"
    fi
}

# 抓取單一頻道的最新影片字幕（含直播）
fetch_channel() {
    local handle="$1"

    echo "=== 正在處理: $handle ==="

    # 分別查詢 /videos 和 /streams，取最新的一支
    local best_meta="" best_url="" best_date=""
    for tab in "videos" "streams"; do
        local url="https://www.youtube.com/${handle}/${tab}"
        local meta
        meta=$(yt-dlp \
            --playlist-items 1 \
            --skip-download \
            --quiet \
            --no-warnings \
            --print "%(upload_date>%Y-%m-%d,unknown)s|%(id)s|%(title)s|%(channel)s" \
            "$url" 2>/dev/null | head -1) || true

        [ -z "$meta" ] && continue

        local d="${meta%%|*}"
        if [ -z "$best_date" ] || [[ "$d" > "$best_date" ]]; then
            best_date="$d"
            best_meta="$meta"
            best_url="$url"
        fi
    done

    if [ -z "$best_meta" ]; then
        echo "  [skip] 無法取得影片資訊"
        echo ""
        return
    fi

    local meta="$best_meta"
    local url="$best_url"
    local date video_id title channel
    IFS='|' read -r date video_id title channel <<< "$meta"

    local date_dir="$SUB_DIR/$date"
    mkdir -p "$date_dir"

    # 寫入 metadata
    echo "$video_id|$title|$date|$channel" > "$date_dir/${handle}_meta.txt"
    echo "  影片：$title ($date)"

    # 依優先順序嘗試下載字幕：台灣繁中 → 簡中 → 英文
    local -a LANG_PRIORITY=("zh-TW" "zh-Hans" "en")

    for lang in "${LANG_PRIORITY[@]}"; do
        local out_file="$date_dir/${handle}_${video_id}.${lang}.vtt"

        # 已存在則直接使用
        if [ -f "$out_file" ]; then
            echo "  [skip] 已有字幕 ($lang)"
            # 若尚未有對應 .txt 則補產生
            local txt_file="${out_file%.vtt}.txt"
            if [ ! -f "$txt_file" ]; then
                uv run "$SCRIPT_DIR/vtt_to_txt.py" "$out_file" || true
            fi
            break
        fi

        # 嘗試下載該語言字幕（手動優先，自動補位）
        yt-dlp \
            --playlist-items 1 \
            --skip-download \
            --write-sub \
            --write-auto-sub \
            --sub-lang "$lang" \
            --convert-subs vtt \
            --output "$date_dir/${handle}_%(id)s" \
            --no-overwrites \
            --ignore-errors \
            "$url" 2>&1 | grep -v "^\[debug\]" || true

        if [ -f "$out_file" ]; then
            echo "  [ok] 字幕已下載 ($lang): $(basename "$out_file")"
            # 轉換為可讀純文字（5 分鐘一段落）
            uv run "$SCRIPT_DIR/vtt_to_txt.py" "$out_file" || true
            break
        fi
    done

    # 若三種語言都無字幕，嘗試 whisper 轉錄
    if ! ls "$date_dir/${handle}_${video_id}".*.vtt 2>/dev/null | grep -q .; then
        transcribe_fallback "$handle" "$video_id" "$date_dir"
    fi

    echo ""
}

# 抓取播放清單最新一支影片的字幕
fetch_playlist() {
    local name="$1"
    local playlist_url="$2"

    echo "=== 正在處理 playlist: $name ==="

    local meta
    meta=$(yt-dlp \
        --playlist-items 1 \
        --skip-download \
        --quiet \
        --no-warnings \
        --print "%(upload_date>%Y-%m-%d,unknown)s|%(id)s|%(title)s|%(channel)s" \
        "$playlist_url" 2>/dev/null | head -1) || true

    if [ -z "$meta" ]; then
        echo "  [skip] 無法取得播放清單資訊"
        echo ""
        return
    fi

    local date video_id title channel
    IFS='|' read -r date video_id title channel <<< "$meta"

    local date_dir="$SUB_DIR/$date"
    mkdir -p "$date_dir"

    echo "$video_id|$title|$date|$channel" > "$date_dir/${name}_meta.txt"
    echo "  影片：$title ($date)"

    local -a LANG_PRIORITY=("zh-TW" "zh-Hans" "en")
    for lang in "${LANG_PRIORITY[@]}"; do
        local out_file="$date_dir/${name}_${video_id}.${lang}.vtt"

        if [ -f "$out_file" ]; then
            echo "  [skip] 已有字幕 ($lang)"
            local txt_file="${out_file%.vtt}.txt"
            if [ ! -f "$txt_file" ]; then
                uv run "$SCRIPT_DIR/vtt_to_txt.py" "$out_file" || true
            fi
            break
        fi

        yt-dlp \
            --playlist-items 1 \
            --skip-download \
            --write-sub \
            --write-auto-sub \
            --sub-lang "$lang" \
            --convert-subs vtt \
            --output "$date_dir/${name}_%(id)s" \
            --no-overwrites \
            --ignore-errors \
            "$playlist_url" 2>&1 | grep -v "^\[debug\]" || true

        if [ -f "$out_file" ]; then
            echo "  [ok] 字幕已下載 ($lang): $(basename "$out_file")"
            uv run "$SCRIPT_DIR/vtt_to_txt.py" "$out_file" || true
            break
        fi
    done

    # 若三種語言都無字幕，嘗試 whisper 轉錄
    if ! ls "$date_dir/${name}_${video_id}".*.vtt 2>/dev/null | grep -q .; then
        transcribe_fallback "$name" "$video_id" "$date_dir"
    fi

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

    # 所有播放清單
    while IFS=' ' read -r name url; do
        fetch_playlist "$name" "$url"
    done < <(get_playlists)
fi

echo "=== 完成 ==="
echo "字幕檔案位於: $SUB_DIR/"
ls -la "$SUB_DIR/" 2>/dev/null || echo "(目錄為空)"
