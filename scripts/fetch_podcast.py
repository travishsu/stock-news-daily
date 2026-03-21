#!/usr/bin/env python3
"""
Fetch latest episodes from podcasts listed in sources/podcasts.txt,
download audio to audios/, transcribe with mlx-whisper,
and output VTT + TXT to subtitles/YYYY-MM-DD/ (same structure as fetch.sh).

Usage:
    uv run scripts/fetch_podcast.py            # all podcasts
    uv run scripts/fetch_podcast.py @gooaye    # single podcast
"""

import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

ROOT = Path(__file__).parent.parent
AUDIOS_DIR = ROOT / "audios"
SUBTITLES_DIR = ROOT / "subtitles"
PODCASTS_TXT = Path(__file__).parent.parent / "sources" / "podcasts.txt"
TRANSCRIBE_PY = Path(__file__).parent / "transcribe.py"


def load_podcasts() -> list[dict]:
    """Parse podcasts.txt and return list of {handle, rss_url, name}."""
    podcasts = []
    for line in PODCASTS_TXT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        podcasts.append({"handle": parts[0], "rss_url": parts[1], "name": parts[2]})
    return podcasts


def fetch_rss(rss_url: str, limit: int = 10) -> list[dict]:
    """Parse RSS and return up to `limit` latest episodes."""
    req = urllib.request.Request(rss_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    channel = root.find("channel")
    episodes = []

    for item in list(channel.findall("item"))[:limit]:
        title = item.findtext("title", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()
        enclosure = item.find("enclosure")
        audio_url = enclosure.attrib.get("url", "") if enclosure is not None else ""

        # Parse pub date → YYYY-MM-DD (RSS uses "GMT" which %z doesn't handle)
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"):
            try:
                pub_dt = datetime.strptime(pub_date_str, fmt)
                break
            except ValueError:
                continue
        else:
            pub_dt = datetime.now(timezone.utc)
        date_str = pub_dt.strftime("%Y-%m-%d")

        # Episode ID from RSS <guid>
        guid = item.findtext("guid", "").strip()
        ep_id = guid.split("/")[-1] if guid else Path(audio_url.split("?")[0]).stem

        episodes.append({"title": title, "date": date_str, "audio_url": audio_url, "ep_id": ep_id})

    return episodes


def already_done(subtitle_dir: Path, handle: str, ep_id: str) -> bool:
    meta = subtitle_dir / f"{handle}_meta.txt"
    if not meta.exists():
        return False
    return ep_id in meta.read_text(encoding="utf-8")


def download_audio(audio_url: str, dest: Path) -> None:
    print(f"  [dl] {dest.name}")
    AUDIOS_DIR.mkdir(exist_ok=True)
    req = urllib.request.Request(audio_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  {pct}%", end="", flush=True)
    print()



def write_meta(subtitle_dir: Path, handle: str, ep_id: str, title: str, date: str, name: str) -> None:
    meta = subtitle_dir / f"{handle}_meta.txt"
    meta.write_text(f"{ep_id}|{title}|{date}|{name}\n", encoding="utf-8")
    print(f"  [meta] {meta.name}")


def process(podcast: dict) -> None:
    handle, rss_url, name = podcast["handle"], podcast["rss_url"], podcast["name"]
    print(f"\n=== {name} ({handle}) ===")

    episodes = fetch_rss(rss_url)
    print(f"  Found {len(episodes)} episode(s)")

    for ep in episodes:
        print(f"  -- {ep['title']} ({ep['date']})")

        subtitle_dir = SUBTITLES_DIR / ep["date"]
        subtitle_dir.mkdir(parents=True, exist_ok=True)

        if already_done(subtitle_dir, handle, ep["ep_id"]):
            print("  Already transcribed, skipping.")
            continue

        audio_path = AUDIOS_DIR / f"{handle}_{ep['ep_id']}.mp3"
        vtt_path = subtitle_dir / f"{handle}_{ep['ep_id']}_zh.vtt"

        if not audio_path.exists():
            download_audio(ep["audio_url"], audio_path)
        else:
            print(f"  [dl] cached {audio_path.name}")

        subprocess.run(
            [sys.executable, str(TRANSCRIBE_PY), str(audio_path), str(vtt_path),
             "--language", "zh", "--txt"],
            check=True,
        )
        write_meta(subtitle_dir, handle, ep["ep_id"], ep["title"], ep["date"], name)
        audio_path.unlink()
        print(f"  [rm] {audio_path.name}")


def main() -> None:
    podcasts = load_podcasts()
    if not podcasts:
        print("No podcasts in podcasts.txt")
        return

    # Filter to specific handle if given as argument
    if len(sys.argv) > 1:
        target = sys.argv[1]
        podcasts = [p for p in podcasts if p["handle"] == target]
        if not podcasts:
            print(f"Handle {target!r} not found in podcasts.txt")
            sys.exit(1)

    for podcast in podcasts:
        process(podcast)

    print("\nDone.")


if __name__ == "__main__":
    main()
