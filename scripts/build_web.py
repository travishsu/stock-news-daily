"""Scan reports/ and notes/ and emit web/manifest.json for the static viewer."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
TIMELINE_DIR = ROOT / "notes" / "stock-timeline"
WEB_DIR = ROOT / "web"

DAILY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
WEEKLY_RE = re.compile(r"^weekly_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.md$")
TW_STOCK_RE = re.compile(r"^(\d{4,6})-(.+)$")


def read_title(path: Path) -> str:
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
                if line:
                    break
    except OSError:
        pass
    return path.stem


def header_field(text: str, label: str) -> str:
    """Pull `**{label}**：value` out of a note's header block."""
    m = re.search(rf"\*\*{label}\*\*[：:]\s*(.+)", text)
    return m.group(1).strip() if m else ""


def parse_timeline(md: Path) -> dict:
    text = md.read_text(encoding="utf-8", errors="replace")
    title = read_title(md)
    stem = md.stem

    if m := TW_STOCK_RE.match(stem):
        ticker, name = m.group(1), m.group(2)
    else:
        ticker = stem.upper()
        name = title.replace("事件時間軸", "").replace(ticker, "").strip() or ticker

    coverage = header_field(text, "涵蓋範圍")
    start, _, end = (p.strip() for p in coverage.partition("～"))

    keywords = header_field(text, "掃描關鍵字").strip("`")
    aliases = [k.strip() for k in keywords.split("|") if k.strip()]

    return {
        "id": ticker,
        "ticker": ticker,
        "name": name,
        "file": md.name,
        "title": title,
        "updated": header_field(text, "最後更新"),
        "start": start,
        "end": end,
        "aliases": aliases,
    }


def build() -> dict:
    daily, weekly = [], []
    for md in sorted(REPORTS_DIR.glob("*.md")):
        name = md.name
        if m := DAILY_RE.match(name):
            daily.append({"date": m.group(1), "file": name, "title": read_title(md)})
            continue
        if m := WEEKLY_RE.match(name):
            weekly.append(
                {
                    "start": m.group(1),
                    "end": m.group(2),
                    "file": name,
                    "title": read_title(md),
                }
            )

    daily.sort(key=lambda r: r["date"], reverse=True)
    weekly.sort(key=lambda r: r["end"], reverse=True)

    stocks = [
        parse_timeline(md)
        for md in sorted(TIMELINE_DIR.glob("*.md"))
        if md.name != "CLAUDE.md"
    ]
    stocks.sort(key=lambda r: r["id"])

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "daily": daily,
        "weekly": weekly,
        "stocks": stocks,
    }


def main() -> None:
    WEB_DIR.mkdir(exist_ok=True)
    manifest = build()
    out = WEB_DIR / "manifest.json"
    out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {out.relative_to(ROOT)} "
        f"({len(manifest['daily'])} daily, {len(manifest['weekly'])} weekly, "
        f"{len(manifest['stocks'])} stocks)"
    )


if __name__ == "__main__":
    main()
