#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parent.parent
MEDIA_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".mp3", ".m4a", ".wav", ".aac", ".flac"}
MODEL_FILE_NAMES = {
    "tiny": "ggml-tiny.bin",
    "base": "ggml-base.bin",
    "small": "ggml-small.bin",
    "medium": "ggml-medium.bin",
    "large": "ggml-large-v3.bin",
    "large-v3": "ggml-large-v3.bin",
}
KNOWN_MODEL_DIRS = [
    Path.home() / "Library/Application Support/com.ngspilot.desktop/runtime-data/tiktok-asr/models",
    Path.home() / "Library/Application Support/NGSpilot/runtime/tiktok-asr/models",
    Path.home() / ".cache/whisper.cpp",
    Path("/opt/homebrew/share/whisper.cpp"),
    SKILL_ROOT / "models" / "whisper",
    SKILL_ROOT.parent / "models" / "whisper",
]


def safe_filename(value: str, fallback: str = "transcript") -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\n\r\t]+', "_", value).strip(" ._")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or fallback)[:160]


def resolve_command(explicit: str, candidates: list[str]) -> str:
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return str(path)
        found = shutil.which(explicit)
        if found:
            return found
        raise SystemExit(f"未找到命令：{explicit}")
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
        path = Path(candidate)
        if path.exists():
            return str(path)
    raise SystemExit(f"未找到命令，请先安装：{', '.join(candidates)}")


def resolve_model(model: str) -> Path:
    env_model = os.environ.get("BGGG_WHISPER_MODEL") or os.environ.get("WHISPER_MODEL")
    candidate = model or env_model or "small"
    candidate_path = Path(candidate).expanduser()
    if candidate_path.exists():
        return candidate_path.resolve()
    file_name = MODEL_FILE_NAMES.get(candidate, candidate)
    for directory in KNOWN_MODEL_DIRS:
        path = directory.expanduser() / file_name
        if path.exists() and path.stat().st_size > 1_000_000:
            return path.resolve()
    searched = "\n".join(str(path.expanduser() / file_name) for path in KNOWN_MODEL_DIRS)
    raise SystemExit(f"未找到 Whisper 模型 {candidate}。已搜索：\n{searched}")


def collect_inputs(paths: list[str], recursive: bool) -> list[Path]:
    result: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"输入不存在：{path}")
        if path.is_file():
            if path.suffix.lower() in MEDIA_EXTENSIONS:
                result.append(path)
            continue
        pattern = "**/*" if recursive else "*"
        for candidate in path.glob(pattern):
            if candidate.is_file() and candidate.suffix.lower() in MEDIA_EXTENSIONS:
                result.append(candidate.resolve())
    return sorted(set(result))


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def parse_whisper_stdout(stdout: str) -> str:
    lines = []
    for line in stdout.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        if trimmed.startswith(("whisper_", "system_info", "main:")):
            continue
        lines.append(trimmed)
    return "\n".join(lines)


def clean_text(value: str) -> str:
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def default_output_dir_for(source: Path) -> Path:
    return source.parent / "transcripts"


def output_prefix(source: Path, output_dir: Path, shared_output: bool) -> Path:
    stem = safe_filename(source.stem)
    if shared_output:
        digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:8]
        stem = f"{stem}-{digest}"
    return output_dir / stem


def extract_audio(ffmpeg: str, source: Path, target: Path) -> None:
    completed = run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            str(target),
        ]
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg 抽取音频失败。")


def transcribe_one(
    source: Path,
    args: argparse.Namespace,
    command: str,
    ffmpeg: str,
    model_path: Path,
    shared_output: bool,
) -> dict[str, Any]:
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else default_output_dir_for(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_prefix(source, output_dir, shared_output)
    transcript_path = prefix.with_suffix(".txt")
    if transcript_path.exists() and not args.force:
        return {
            "sourcePath": str(source),
            "transcriptPath": str(transcript_path),
            "status": "skipped",
            "message": "transcript already exists",
        }

    with tempfile.TemporaryDirectory(prefix="bggg-whisper-") as temp_dir:
        audio_path = Path(temp_dir) / "audio.wav"
        extract_audio(ffmpeg, source, audio_path)
        whisper_args = [
            command,
            "-m",
            str(model_path),
            "-f",
            str(audio_path),
            "-l",
            args.language,
            "-otxt",
        ]
        if args.srt:
            whisper_args.append("-osrt")
        if args.json:
            whisper_args.append("-oj")
        whisper_args.extend(["-of", str(prefix)])
        completed = run_command(whisper_args)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "whisper.cpp 转写失败。")
        text = transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else parse_whisper_stdout(completed.stdout)
        transcript_path.write_text(clean_text(text), encoding="utf-8")

    item = {
        "sourcePath": str(source),
        "transcriptPath": str(transcript_path),
        "status": "done",
        "language": args.language,
        "modelPath": str(model_path),
    }
    srt_path = prefix.with_suffix(".srt")
    json_path = prefix.with_suffix(".json")
    if srt_path.exists():
        item["srtPath"] = str(srt_path)
    if json_path.exists():
        item["jsonPath"] = str(json_path)
    return item


def write_manifest(items: list[dict[str, Any]], output_dir: Path, model_path: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "transcription_manifest.json"
    manifest = {
        "jobId": f"bggg-readvideo-transcribe-{int(time.time() * 1000)}",
        "skillRoot": str(SKILL_ROOT),
        "itemCount": len(items),
        "modelPath": str(model_path),
        "manifestPath": str(manifest_path),
        "items": items,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe video/audio tracks with local whisper.cpp models for bggg-tiktok-readvideo."
    )
    parser.add_argument("inputs", nargs="+", help="Video/audio files or folders.")
    parser.add_argument("--recursive", action="store_true", help="Recurse into input folders.")
    parser.add_argument("--output-dir", default="", help="Directory for transcripts. Defaults to each source folder's transcripts/.")
    parser.add_argument("--model", default="", help="Model id (tiny/base/small/...) or path to ggml model.")
    parser.add_argument("--command", default="", help="whisper-cli or whisper-cpp path.")
    parser.add_argument("--ffmpeg", default="", help="ffmpeg path.")
    parser.add_argument("--language", default="auto", help="Whisper language code. Use auto to preserve original language.")
    parser.add_argument("--srt", action="store_true", help="Also emit .srt subtitles.")
    parser.add_argument("--json", action="store_true", help="Also emit whisper.cpp JSON.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing transcripts.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sources = collect_inputs(args.inputs, args.recursive)
    if not sources:
        raise SystemExit("没有找到可转写的视频或音频文件。")
    command = resolve_command(
        args.command,
        [
            "whisper-cli",
            "whisper-cpp",
            "whisper.cpp",
            "/opt/homebrew/bin/whisper-cli",
            "/usr/local/bin/whisper-cli",
            "/opt/homebrew/bin/whisper-cpp",
            "/usr/local/bin/whisper-cpp",
        ],
    )
    ffmpeg = resolve_command(args.ffmpeg, ["ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"])
    model_path = resolve_model(args.model)
    shared_output = bool(args.output_dir) or len(sources) > 1
    items: list[dict[str, Any]] = []
    for source in sources:
        try:
            items.append(transcribe_one(source, args, command, ffmpeg, model_path, shared_output))
        except Exception as error:
            items.append({"sourcePath": str(source), "status": "error", "error": str(error)})
    manifest_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else default_output_dir_for(sources[0])
    manifest = write_manifest(items, manifest_dir, model_path)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
