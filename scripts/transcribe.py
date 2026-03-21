#!/usr/bin/env python3
"""
Standalone whisper transcription CLI.

Usage:
    uv run scripts/transcribe.py <audio_file> <output_vtt> [--language zh] [--model ...] [--txt]

Options:
    --language  Whisper language code (default: zh)
    --model     HuggingFace repo or local path for mlx-whisper
    --txt       Also produce a .txt file via vtt_to_txt.py
"""

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
VTT_TO_TXT = Path(__file__).parent / "vtt_to_txt.py"


def fmt_vtt_ts(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio to VTT using mlx-whisper")
    parser.add_argument("audio_file", help="Input audio file path")
    parser.add_argument("output_vtt", help="Output VTT file path")
    parser.add_argument("--language", default="zh", help="Whisper language code (default: zh)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="mlx-whisper model repo or path")
    parser.add_argument("--txt", action="store_true", help="Also produce .txt via vtt_to_txt.py")
    args = parser.parse_args()

    audio_path = Path(args.audio_file)
    vtt_path = Path(args.output_vtt)

    if not audio_path.exists():
        print(f"ERROR: audio file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    import mlx_whisper

    print(f"  [whisper] transcribing {audio_path.name} (lang={args.language}) ...")
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=args.model,
        word_timestamps=False,
        language=args.language,
        verbose=False,
    )

    segments = result.get("segments", [])
    if not segments:
        print("ERROR: no segments produced", file=sys.stderr)
        sys.exit(2)

    vtt_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["WEBVTT", ""]
    for seg in segments:
        text = seg["text"].strip()
        if text:
            lines += [f"{fmt_vtt_ts(seg['start'])} --> {fmt_vtt_ts(seg['end'])}", text, ""]
    vtt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [vtt] {vtt_path.name} ({len(segments)} segments)")

    if args.txt:
        ret = subprocess.run([sys.executable, str(VTT_TO_TXT), str(vtt_path)], check=False)
        if ret.returncode != 0:
            sys.exit(3)


if __name__ == "__main__":
    main()
