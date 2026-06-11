#!/usr/bin/env python3
"""Optional local transcription helper for captions and cut decisions.

Uses faster-whisper when installed; otherwise falls back to the `whisper` CLI.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from media_common import require_binary, run


def srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list[dict], out_path: Path) -> None:
    lines: list[str] = []
    for index, seg in enumerate(segments, 1):
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        lines.extend(
            [
                str(index),
                f"{srt_time(float(seg['start']))} --> {srt_time(float(seg['end']))}",
                text,
                "",
            ]
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def extract_audio(source: Path, out_wav: Path) -> None:
    require_binary("ffmpeg")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(out_wav),
        ]
    )


def transcribe_faster_whisper(audio: Path, model_name: str, language: str | None) -> dict:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed") from exc

    model = WhisperModel(model_name, device="auto", compute_type="auto")
    kwargs = {"word_timestamps": True, "vad_filter": True}
    if language and language != "auto":
        kwargs["language"] = language
    segments_iter, info = model.transcribe(str(audio), **kwargs)
    segments = []
    for idx, seg in enumerate(segments_iter):
        words = []
        for word in seg.words or []:
            words.append({"start": word.start, "end": word.end, "word": word.word})
        segments.append(
            {
                "id": idx,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
                "words": words,
            }
        )
    return {
        "engine": "faster-whisper",
        "model": model_name,
        "language": getattr(info, "language", language or "auto"),
        "duration": getattr(info, "duration", None),
        "segments": segments,
    }


def transcribe_whisper_cli(audio: Path, model_name: str, language: str | None, out_dir: Path) -> dict:
    if shutil.which("whisper") is None:
        raise RuntimeError("Neither faster-whisper nor whisper CLI is available.")
    cmd = [
        "whisper",
        str(audio),
        "--model",
        model_name,
        "--word_timestamps",
        "True",
        "--output_format",
        "json",
        "--output_dir",
        str(out_dir),
    ]
    if language and language != "auto":
        cmd.extend(["--language", language])
    run(cmd)
    json_path = out_dir / f"{audio.stem}.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    data.setdefault("engine", "whisper-cli")
    data.setdefault("model", model_name)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe a video/audio file for bggg-tiktok-cut.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--out-dir", type=Path, help="Output directory. Defaults to sibling transcripts/.")
    parser.add_argument("--model", default="small", help="Whisper model name.")
    parser.add_argument("--language", default="auto", help="Language code, or auto.")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")
    out_dir = args.out_dir.expanduser().resolve() if args.out_dir else source.parent.parent / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    audio = out_dir / f"{source.stem}.wav"
    extract_audio(source, audio)

    language = args.language if args.language != "auto" else None
    try:
        result = transcribe_faster_whisper(audio, args.model, language)
    except RuntimeError:
        result = transcribe_whisper_cli(audio, args.model, language, out_dir)

    json_path = out_dir / f"{source.stem}.json"
    srt_path = out_dir / f"{source.stem}.srt"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_srt(result.get("segments", []), srt_path)
    print(json.dumps({"json": str(json_path), "srt": str(srt_path)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
