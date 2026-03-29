#!/usr/bin/env python3
"""
Convert a VTT subtitle file into a readable text file.
Groups captions into 5-minute paragraphs, sentences separated by spaces.
Deduplicates overlapping/rolling captions common in auto-generated subtitles.

Usage:
    python scripts/vtt_to_txt.py <input.vtt> [output.txt]
    If output.txt is omitted, writes alongside input with .txt extension.
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_DEFAULT_INTERVAL = int(os.environ.get("VTT_PARAGRAPH_INTERVAL", "300"))


def parse_timestamp(ts: str) -> float:
    """Convert HH:MM:SS.mmm or MM:SS.mmm to seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
    else:
        h, m, s = 0, parts[0], parts[1]
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_vtt(path: Path) -> list[tuple[float, str]]:
    """Return list of (start_seconds, text) for each cue."""
    cues = []
    text = path.read_text(encoding="utf-8", errors="replace")

    # Split on blank lines to get cue blocks
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue
        # Find the timestamp line
        ts_line = None
        ts_idx = None
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_line = line
                ts_idx = i
                break
        if ts_line is None:
            continue
        start_str = ts_line.split("-->")[0].strip()
        # Remove any cue settings after the timestamp (position, align, etc.)
        start_str = start_str.split()[0]
        try:
            start = parse_timestamp(start_str)
        except (ValueError, IndexError):
            continue
        # Text is everything after the timestamp line
        content_lines = lines[ts_idx + 1 :]
        text_content = " ".join(content_lines)
        # Strip VTT tags like <c>, </c>, <00:00:01.000>
        text_content = re.sub(r"<[^>]+>", "", text_content).strip()
        if text_content:
            cues.append((start, text_content))

    return cues


def deduplicate(cues: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Remove consecutive duplicate or fully-contained texts (rolling captions)."""
    result = []
    prev_text = None
    for start, text in cues:
        if text == prev_text:
            continue
        # Skip if new text is just a suffix of previous (rolling caption)
        if prev_text and prev_text.endswith(text) and len(text) < len(prev_text):
            continue
        result.append((start, text))
        prev_text = text
    return result


def fmt_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def group_into_paragraphs(
    cues: list[tuple[float, str]], interval: int = _DEFAULT_INTERVAL, line_interval: int = 60
) -> list[str]:
    """Group cues into chunks of `interval` seconds (default 5 min).
    Within each chunk, cues are grouped into lines of `line_interval` seconds (default 1 min).
    Returns one string per chunk; each string has one line per minute sub-bucket.
    """
    if not cues:
        return []

    # Build a dict: chunk_bucket -> {line_bucket -> (first_start, [texts])}
    chunks: dict[int, dict[int, tuple[float, list[str]]]] = {}
    for start, text in cues:
        c_bucket = int(start // interval)
        l_bucket = int(start // line_interval)
        if c_bucket not in chunks:
            chunks[c_bucket] = {}
        if l_bucket not in chunks[c_bucket]:
            chunks[c_bucket][l_bucket] = (start, [])
        chunks[c_bucket][l_bucket][1].append(text)

    paragraphs = []
    for c_bucket in sorted(chunks):
        lines = []
        for l_bucket in sorted(chunks[c_bucket]):
            first_start, texts = chunks[c_bucket][l_bucket]
            label = fmt_timestamp(first_start)
            lines.append(f"[{label}] " + " ".join(texts))
        paragraphs.append("\n".join(lines))

    return paragraphs


def write_chunks(paragraphs: list[str], base_path: Path) -> None:
    """Write each paragraph to its own file named {stem}_{HH-MM-SS}.txt."""
    parent = base_path.parent
    stem = base_path.stem   # e.g. "@channel_video.zh"
    suffix = base_path.suffix  # ".txt"

    for para in paragraphs:
        m = re.match(r"^\[(\d{2}):(\d{2}):(\d{2})\]", para)
        ts = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else "00-00-00"
        chunk_path = parent / f"{stem}_{ts}{suffix}"
        chunk_path.write_text(para + "\n", encoding="utf-8")


def convert(input_path: Path, output_path: Path, interval: int = _DEFAULT_INTERVAL) -> None:
    cues = parse_vtt(input_path)
    cues = deduplicate(cues)
    paragraphs = group_into_paragraphs(cues, interval)
    output_path.write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")
    write_chunks(paragraphs, output_path)
    print(f"  [txt] {output_path.name} ({len(paragraphs)} paragraphs)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else input_path.with_suffix(".txt")

    if not input_path.exists():
        print(f"ERROR: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    convert(input_path, output_path)
