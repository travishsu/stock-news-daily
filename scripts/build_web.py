"""Scan reports/ and emit web/manifest.json for the static viewer."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
WEB_DIR = ROOT / "web"

DAILY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
WEEKLY_RE = re.compile(r"^weekly_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.md$")


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

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "daily": daily,
        "weekly": weekly,
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
        f"({len(manifest['daily'])} daily, {len(manifest['weekly'])} weekly)"
    )


if __name__ == "__main__":
    main()
