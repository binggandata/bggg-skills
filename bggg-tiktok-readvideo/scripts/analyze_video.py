#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


SKILL_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_ROOT = SKILL_ROOT / "projects"
MEDIA_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}

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
]


def run_command(args: Sequence[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False, timeout=timeout)


def resolve_command(explicit: str, candidates: Sequence[str], *, required: bool = True) -> str | None:
    if explicit:
        expanded = Path(explicit).expanduser()
        if expanded.exists():
            return str(expanded)
        found = shutil.which(explicit)
        if found:
            return found
        if required:
            raise SystemExit(f"Command not found: {explicit}")
        return None

    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
        path = Path(candidate).expanduser()
        if path.exists():
            return str(path)

    if required:
        raise SystemExit(f"Command not found. Install one of: {', '.join(candidates)}")
    return None


def slugify(value: str, fallback: str = "video") -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return (text or fallback)[:90]


def safe_file_stem(value: str, fallback: str = "video") -> str:
    text = re.sub(r'[\\/:*?"<>|\n\r\t]+', "_", value).strip(" ._")
    text = re.sub(r"\s+", " ", text)
    return (text or fallback)[:140]


def unique_project_dir(date_prefix: str, slug: str) -> Path:
    base = PROJECTS_ROOT / f"{date_prefix}_{slug}"
    if not base.exists():
        return base
    index = 2
    while True:
        candidate = PROJECTS_ROOT / f"{date_prefix}_{slug}_{index}"
        if not candidate.exists():
            return candidate
        index += 1


def seconds_to_hms(seconds: float | int | None) -> str:
    if seconds is None or not math.isfinite(float(seconds)):
        return "unknown"
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"
    return f"{minutes:02d}:{secs:05.2f}"


def seconds_to_srt(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    millis = int(round((seconds - int(seconds)) * 1000))
    whole = int(seconds)
    if millis == 1000:
        whole += 1
        millis = 0
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def ffprobe_metadata(video_path: Path, ffprobe: str) -> dict[str, Any]:
    result = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")

    raw = json.loads(result.stdout)
    streams = raw.get("streams") if isinstance(raw.get("streams"), list) else []
    format_info = raw.get("format") if isinstance(raw.get("format"), dict) else {}
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), {})

    def parse_fps(rate: str | None) -> float | None:
        if not rate or "/" not in rate:
            return None
        left, right = rate.split("/", 1)
        try:
            numerator = float(left)
            denominator = float(right)
            return None if denominator == 0 else numerator / denominator
        except ValueError:
            return None

    duration = None
    if format_info.get("duration"):
        try:
            duration = float(format_info["duration"])
        except ValueError:
            duration = None

    normalized = {
        "duration_sec": duration,
        "duration_hms": seconds_to_hms(duration),
        "format_name": format_info.get("format_name", ""),
        "size_bytes": int(format_info["size"]) if str(format_info.get("size", "")).isdigit() else None,
        "bit_rate": int(format_info["bit_rate"]) if str(format_info.get("bit_rate", "")).isdigit() else None,
        "video": {
            "codec": video_stream.get("codec_name", ""),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "fps": parse_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
            "avg_frame_rate": video_stream.get("avg_frame_rate", ""),
            "rotation": video_stream.get("tags", {}).get("rotate", ""),
        },
        "audio": {
            "available": bool(audio_stream),
            "codec": audio_stream.get("codec_name", ""),
            "sample_rate": int(audio_stream["sample_rate"]) if str(audio_stream.get("sample_rate", "")).isdigit() else None,
            "channels": audio_stream.get("channels"),
        },
    }
    return {"normalized": normalized, "raw": raw}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def link_or_copy_source(source: Path, raw_dir: Path, *, copy_input: bool) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / f"input{source.suffix.lower()}"
    if target.exists() or target.is_symlink():
        target.unlink()
    if copy_input:
        shutil.copy2(source, target)
        return target
    try:
        target.symlink_to(source)
    except OSError:
        shutil.copy2(source, target)
    return target


def resolve_model(model: str) -> Path | None:
    candidate = model or os.environ.get("BGGG_WHISPER_MODEL") or os.environ.get("WHISPER_MODEL") or "small"
    candidate_path = Path(candidate).expanduser()
    if candidate_path.exists():
        return candidate_path.resolve()
    file_name = MODEL_FILE_NAMES.get(candidate, candidate)
    for directory in KNOWN_MODEL_DIRS:
        path = directory.expanduser() / file_name
        if path.exists() and path.stat().st_size > 1_000_000:
            return path.resolve()
    return None


def extract_audio(ffmpeg: str, source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
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
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg audio extraction failed")


def clean_transcript_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def parse_srt(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n\s*\n", content.strip())
    segments: list[dict[str, Any]] = []
    time_re = re.compile(
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
    )

    def to_seconds(match: re.Match[str], offset: int) -> float:
        hours = int(match.group(offset))
        minutes = int(match.group(offset + 1))
        secs = int(match.group(offset + 2))
        millis = int(match.group(offset + 3))
        return hours * 3600 + minutes * 60 + secs + millis / 1000

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        match = time_re.search("\n".join(lines[:2]))
        if not match:
            continue
        text_lines = lines[2:] if lines[0].isdigit() else lines[1:]
        text = clean_transcript_text(" ".join(text_lines))
        if text:
            segments.append({"start": to_seconds(match, 1), "end": to_seconds(match, 5), "text": text})
    return segments


def transcribe_video(
    source: Path,
    analysis_dir: Path,
    ffmpeg: str,
    args: argparse.Namespace,
    warnings: list[str],
) -> dict[str, Any]:
    transcript_dir = analysis_dir
    prefix = transcript_dir / "transcript"
    result: dict[str, Any] = {
        "available": False,
        "status": "skipped",
        "text_path": str(prefix.with_suffix(".txt")),
        "srt_path": str(prefix.with_suffix(".srt")),
        "json_path": str(prefix.with_suffix(".json")),
        "segments": [],
    }
    if not args.transcribe:
        result["reason"] = "transcription disabled"
        return result

    command = resolve_command(
        args.whisper_command,
        [
            "whisper-cli",
            "whisper-cpp",
            "whisper.cpp",
            "/opt/homebrew/bin/whisper-cli",
            "/usr/local/bin/whisper-cli",
            "/opt/homebrew/bin/whisper-cpp",
            "/usr/local/bin/whisper-cpp",
        ],
        required=False,
    )
    if not command:
        result["reason"] = "whisper.cpp command not found"
        warnings.append("Transcription skipped: whisper-cli/whisper-cpp was not found.")
        return result

    model_path = resolve_model(args.model)
    if not model_path:
        result["reason"] = f"Whisper model not found: {args.model or 'small'}"
        warnings.append("Transcription skipped: no local whisper.cpp ggml model was found.")
        return result

    try:
        audio_path = analysis_dir / "audio.wav"
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
            "-osrt",
            "-oj",
            "-of",
            str(prefix),
        ]
        completed = run_command(whisper_args)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "whisper.cpp failed")

        txt_path = prefix.with_suffix(".txt")
        if txt_path.exists():
            txt_path.write_text(clean_transcript_text(txt_path.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")

        segments = parse_srt(prefix.with_suffix(".srt"))
        result.update(
            {
                "available": bool(txt_path.exists() or segments),
                "status": "done",
                "backend": Path(command).name,
                "model_path": str(model_path),
                "language": args.language,
                "audio_path": str(audio_path),
                "segments": segments,
            }
        )
        return result
    except Exception as error:
        warnings.append(f"Transcription failed: {error}")
        result["status"] = "error"
        result["error"] = str(error)
        return result


def detect_scene_times(
    source: Path,
    ffmpeg: str,
    duration: float,
    threshold: float,
    max_frames: int,
    min_interval: float,
    fallback_interval: float,
    warnings: list[str],
) -> list[float]:
    scene_times: list[float] = []
    result = run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(source),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-vsync",
            "vfr",
            "-f",
            "null",
            "-",
        ]
    )
    if result.returncode == 0 or result.stderr:
        for match in re.finditer(r"pts_time:\s*([0-9.]+)", result.stderr):
            value = float(match.group(1))
            if value <= 0.05:
                continue
            if scene_times and value - scene_times[-1] < min_interval:
                continue
            scene_times.append(round(value, 3))
            if len(scene_times) >= max_frames - 1:
                break
    else:
        warnings.append("Scene detection failed; falling back to interval frames.")

    if not scene_times:
        interval = max(1.0, fallback_interval)
        count = max(1, min(max_frames - 1, int(duration // interval)))
        scene_times = [round(min(duration - 0.05, interval * i), 3) for i in range(1, count + 1)]

    times = [0.0]
    for value in scene_times:
        if value < duration - 0.05 and (not times or value - times[-1] >= min_interval):
            times.append(value)
    if duration > 0 and duration - times[-1] >= 0.25:
        times.append(round(duration, 3))
    return times


def build_scenes(times: list[float], transcript_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for index in range(max(0, len(times) - 1)):
        start = times[index]
        end = times[index + 1]
        text = transcript_excerpt(transcript_segments, start, end, max_chars=260)
        scenes.append(
            {
                "id": index + 1,
                "start": start,
                "end": end,
                "duration": round(max(0.0, end - start), 3),
                "start_hms": seconds_to_hms(start),
                "end_hms": seconds_to_hms(end),
                "transcript_excerpt": text,
            }
        )
    return scenes


def transcript_excerpt(segments: list[dict[str, Any]], start: float, end: float, *, max_chars: int) -> str:
    pieces: list[str] = []
    for segment in segments:
        seg_start = float(segment.get("start", 0))
        seg_end = float(segment.get("end", seg_start))
        if seg_end < start or seg_start > end:
            continue
        text = str(segment.get("text", "")).strip()
        if text:
            pieces.append(text)
    joined = " ".join(pieces).strip()
    if len(joined) > max_chars:
        return joined[: max_chars - 1].rstrip() + "..."
    return joined


def escape_drawtext(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def label_frame(ffmpeg: str, source_frame: Path, target_frame: Path, label: str) -> bool:
    draw = (
        "drawtext="
        f"text='{escape_drawtext(label)}':"
        "x=14:y=14:"
        "fontcolor=white:"
        "fontsize=28:"
        "box=1:"
        "boxcolor=black@0.68:"
        "boxborderw=8"
    )
    result = run_command([ffmpeg, "-y", "-i", str(source_frame), "-vf", draw, "-q:v", "2", str(target_frame)])
    return result.returncode == 0 and target_frame.exists()


def extract_keyframes(
    source: Path,
    ffmpeg: str,
    scenes: list[dict[str, Any]],
    duration: float,
    keyframes_dir: Path,
    warnings: list[str],
) -> list[dict[str, Any]]:
    raw_dir = keyframes_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    keyframes_dir.mkdir(parents=True, exist_ok=True)
    frames: list[dict[str, Any]] = []

    for scene in scenes:
        index = int(scene["id"])
        start = float(scene["start"])
        seek = min(max(0.0, start + 0.08), max(0.0, duration - 0.05))
        raw_path = raw_dir / f"frame_{index:04d}.jpg"
        frame_path = keyframes_dir / f"frame_{index:04d}.jpg"
        result = run_command(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{seek:.3f}",
                "-i",
                str(source),
                "-vframes",
                "1",
                "-vf",
                "scale=720:-2",
                "-q:v",
                "2",
                str(raw_path),
            ]
        )
        if result.returncode != 0 or not raw_path.exists():
            warnings.append(f"Failed to extract keyframe for scene {index}: {result.stderr.strip()[:240]}")
            continue

        label = f"{index:02d} {seconds_to_hms(start)}"
        if not label_frame(ffmpeg, raw_path, frame_path, label):
            shutil.copy2(raw_path, frame_path)

        scene["keyframe"] = str(frame_path)
        frames.append(
            {
                "scene_id": index,
                "time_sec": start,
                "time_hms": seconds_to_hms(start),
                "path": str(frame_path),
                "raw_path": str(raw_path),
            }
        )
    return frames


def build_contact_sheet(
    ffmpeg: str,
    keyframes: list[dict[str, Any]],
    output_path: Path,
    *,
    columns: int,
    thumb_width: int,
    warnings: list[str],
) -> None:
    if not keyframes:
        warnings.append("Contact sheet skipped: no keyframes were extracted.")
        return
    columns = max(1, min(columns, len(keyframes)))
    rows = int(math.ceil(len(keyframes) / columns))
    with tempfile.TemporaryDirectory(prefix="bggg-sheet-") as temp:
        temp_dir = Path(temp)
        for index, frame in enumerate(keyframes, start=1):
            shutil.copy2(frame["path"], temp_dir / f"sheet_{index:04d}.jpg")
        result = run_command(
            [
                ffmpeg,
                "-y",
                "-framerate",
                "1",
                "-i",
                str(temp_dir / "sheet_%04d.jpg"),
                "-vf",
                f"scale={thumb_width}:-2,tile={columns}x{rows}:padding=8:margin=8:color=0x111111",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(output_path),
            ]
        )
    if result.returncode != 0 or not output_path.exists():
        warnings.append(f"Contact sheet generation failed: {result.stderr.strip()[:300]}")


def analyze_audio_events(source: Path, ffmpeg: str, has_audio: bool, output_path: Path, warnings: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": bool(has_audio),
        "silence": [],
        "volume": {},
        "notes": [],
    }
    if not has_audio:
        payload["notes"].append("No audio stream found.")
        write_json(output_path, payload)
        return payload

    silence_result = run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(source),
            "-af",
            "silencedetect=n=-35dB:d=0.6",
            "-f",
            "null",
            "-",
        ]
    )
    silence_starts: list[float] = []
    for line in silence_result.stderr.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        end_match = re.search(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", line)
        if start_match:
            silence_starts.append(float(start_match.group(1)))
        if end_match:
            start = silence_starts.pop(0) if silence_starts else None
            payload["silence"].append(
                {
                    "start": start,
                    "end": float(end_match.group(1)),
                    "duration": float(end_match.group(2)),
                }
            )

    volume_result = run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(source),
            "-af",
            "volumedetect",
            "-vn",
            "-sn",
            "-dn",
            "-f",
            "null",
            "-",
        ]
    )
    for key in ("mean_volume", "max_volume"):
        match = re.search(rf"{key}:\s*([-0-9.]+)\s*dB", volume_result.stderr)
        if match:
            payload["volume"][key] = float(match.group(1))
    if silence_result.returncode != 0:
        warnings.append("Audio silence detection returned a non-zero exit code; partial audio_events.json was written.")
    write_json(output_path, payload)
    return payload


def run_ocr(
    keyframes: list[dict[str, Any]],
    output_path: Path,
    *,
    mode: str,
    language: str,
    max_frames: int,
    warnings: list[str],
) -> dict[str, Any]:
    tesseract = resolve_command("", ["tesseract"], required=False)
    payload: dict[str, Any] = {
        "status": "skipped",
        "engine": "tesseract",
        "language": language,
        "items": [],
    }
    if mode == "off":
        payload["reason"] = "OCR disabled"
        write_json(output_path, payload)
        return payload
    if not tesseract:
        payload["reason"] = "tesseract not found"
        if mode == "on":
            warnings.append("OCR requested but tesseract was not found.")
        write_json(output_path, payload)
        return payload

    requested_language = language
    listed = run_command([tesseract, "--list-langs"])
    available = {
        line.strip()
        for line in listed.stdout.splitlines()
        if line.strip() and not line.lower().startswith("list of available")
    }
    if available:
        requested_parts = [part for part in language.split("+") if part]
        usable_parts = [part for part in requested_parts if part in available]
        missing_parts = [part for part in requested_parts if part not in available]
        if missing_parts:
            fallback = "eng" if "eng" in available else (sorted(available)[0] if available else language)
            language = "+".join(usable_parts) if usable_parts else fallback
            payload["requested_language"] = requested_language
            payload["language"] = language
            payload["missing_languages"] = missing_parts
            warnings.append(f"OCR language fallback: missing {', '.join(missing_parts)}; using {language}.")

    for frame in keyframes[: max(1, max_frames)]:
        completed = run_command([tesseract, frame["path"], "stdout", "-l", language], timeout=60)
        text = clean_transcript_text(completed.stdout)
        payload["items"].append(
            {
                "scene_id": frame["scene_id"],
                "time_sec": frame["time_sec"],
                "path": frame["path"],
                "text": text,
                "status": "done" if completed.returncode == 0 else "error",
                "error": completed.stderr.strip()[:500] if completed.returncode != 0 else "",
            }
        )
    payload["status"] = "done"
    write_json(output_path, payload)
    return payload


def write_timeline(
    path: Path,
    source: Path,
    metadata: dict[str, Any],
    scenes: list[dict[str, Any]],
    keyframes: list[dict[str, Any]],
    assets: dict[str, str],
    warnings: list[str],
) -> None:
    normalized = metadata["normalized"]
    video = normalized.get("video", {})
    audio = normalized.get("audio", {})
    lines = [
        "# Video Timeline Context",
        "",
        f"- Source: `{source}`",
        f"- Duration: {normalized.get('duration_hms')} ({normalized.get('duration_sec')} sec)",
        f"- Resolution: {video.get('width')}x{video.get('height')} @ {video.get('fps') or 'unknown'} fps",
        f"- Video codec: {video.get('codec') or 'unknown'}",
        f"- Audio: {'yes' if audio.get('available') else 'no'} ({audio.get('codec') or 'none'})",
        "",
        "## Assets for Codex",
        "",
        f"- Metadata: `{assets['metadata']}`",
        f"- Scenes: `{assets['scenes']}`",
        f"- Transcript TXT: `{assets['transcript_txt']}`",
        f"- Transcript SRT: `{assets['transcript_srt']}`",
        f"- Contact sheet image: `{assets['contact_sheet']}`",
        f"- Keyframes index: `{assets['keyframes_index']}`",
        f"- Audio events: `{assets['audio_events']}`",
        f"- OCR: `{assets['ocr']}`",
        "",
        "## Reading Instructions",
        "",
        "1. Do not infer content from the filename alone.",
        "2. Inspect the contact sheet first for visual structure, products, screenshots, text overlays, people, and scene changes.",
        "3. Read transcript and scene rows together; timestamps are the source of truth for edit decisions.",
        "4. For TikTok edits, produce `output/edit_plan.json` before rendering.",
        "",
        "## Scene Timeline",
        "",
        "| # | Time | Duration | Keyframe | Transcript excerpt |",
        "|---|---:|---:|---|---|",
    ]
    frame_by_scene = {item["scene_id"]: item for item in keyframes}
    for scene in scenes:
        frame = frame_by_scene.get(scene["id"], {})
        excerpt = str(scene.get("transcript_excerpt") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {scene['id']} | {scene['start_hms']} - {scene['end_hms']} | "
            f"{scene['duration']:.2f}s | `{frame.get('path', '')}` | {excerpt or '-'} |"
        )

    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_edit_plan_template(output_dir: Path, source_video: Path, analysis_manifest: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "edit_plan.template.json"
    payload = {
        "source_video": str(source_video),
        "analysis_manifest": str(analysis_manifest),
        "goal": "TikTok 9:16 short video",
        "output": str(output_dir / "final_tiktok_9x16.mp4"),
        "defaults": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "fit": "cover",
            "burn_captions": True,
            "caption_source_timeline": True,
        },
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "label": "hook",
                "reason": "Replace with the strongest opening moment after reading timeline.md.",
            }
        ],
        "captions": [],
        "notes": [
            "Copy this file to edit_plan.json and replace segments with deliberate edit choices before rendering.",
            "Segment start/end values use source-video timestamps.",
        ],
    }
    write_json(path, payload)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Turn a video into Codex-readable context assets for TikTok analysis/editing.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", help="Input video path.")
    parser.add_argument("--slug", default="", help="Project slug. Defaults to input filename.")
    parser.add_argument("--date", default="", help="YYYYMMDD prefix. Defaults to local date.")
    parser.add_argument("--project-dir", default="", help="Explicit output project directory.")
    parser.add_argument("--copy-input", action="store_true", help="Copy input into raw/ instead of symlinking.")
    parser.add_argument("--ffmpeg", default="", help="ffmpeg path.")
    parser.add_argument("--ffprobe", default="", help="ffprobe path.")
    parser.add_argument("--max-frames", type=int, default=36, help="Maximum scene keyframes to extract.")
    parser.add_argument("--scene-threshold", type=float, default=0.28, help="FFmpeg scene threshold, 0-1.")
    parser.add_argument("--min-scene-interval", type=float, default=1.0, help="Minimum seconds between scene frames.")
    parser.add_argument("--fallback-interval", type=float, default=3.0, help="Interval fallback when scene detection finds no cuts.")
    parser.add_argument("--sheet-columns", type=int, default=4, help="Contact sheet columns.")
    parser.add_argument("--sheet-thumb-width", type=int, default=360, help="Contact sheet thumbnail width.")
    parser.add_argument("--no-transcribe", dest="transcribe", action="store_false", help="Skip Whisper transcription.")
    parser.set_defaults(transcribe=True)
    parser.add_argument("--whisper-command", default="", help="whisper-cli/whisper-cpp path.")
    parser.add_argument("--model", default="", help="Whisper model id or ggml model path.")
    parser.add_argument("--language", default="auto", help="Whisper language code; auto keeps original language.")
    parser.add_argument("--ocr", choices=["auto", "on", "off"], default="auto", help="Run OCR if tesseract is available.")
    parser.add_argument("--ocr-language", default="eng", help="Tesseract language list, e.g. eng or eng+chi_sim.")
    parser.add_argument("--ocr-max-frames", type=int, default=20, help="Maximum keyframes to OCR.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Input not found: {source}")
    if source.suffix.lower() not in MEDIA_EXTENSIONS:
        raise SystemExit(f"Unsupported video extension: {source.suffix}")

    ffmpeg = resolve_command(args.ffmpeg, ["ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"])
    ffprobe = resolve_command(args.ffprobe, ["ffprobe", "/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"])

    date_prefix = args.date or datetime.now().strftime("%Y%m%d")
    slug = slugify(args.slug or source.stem, "readvideo")
    project_dir = Path(args.project_dir).expanduser().resolve() if args.project_dir else unique_project_dir(date_prefix, slug)
    raw_dir = project_dir / "raw"
    analysis_dir = project_dir / "analysis"
    output_dir = project_dir / "output"
    keyframes_dir = analysis_dir / "keyframes"
    for directory in [raw_dir, analysis_dir, output_dir, keyframes_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    started = time.time()
    project_source = link_or_copy_source(source, raw_dir, copy_input=args.copy_input)

    metadata = ffprobe_metadata(source, ffprobe)
    metadata_path = analysis_dir / "metadata.json"
    write_json(metadata_path, metadata)

    duration = float(metadata["normalized"].get("duration_sec") or 0)
    if duration <= 0:
        raise SystemExit("Could not determine video duration.")

    transcript = transcribe_video(source, analysis_dir, ffmpeg, args, warnings)
    transcript_txt_path = analysis_dir / "transcript.txt"
    transcript_srt_path = analysis_dir / "transcript.srt"
    if not transcript_txt_path.exists():
        reason = transcript.get("reason") or transcript.get("error") or "transcription did not produce text"
        transcript_txt_path.write_text(f"[Transcription unavailable: {reason}]\n", encoding="utf-8")
    if not transcript_srt_path.exists():
        transcript_srt_path.write_text("", encoding="utf-8")
    transcript_segments = transcript.get("segments", []) if isinstance(transcript.get("segments"), list) else []

    times = detect_scene_times(
        source,
        ffmpeg,
        duration,
        args.scene_threshold,
        max(2, args.max_frames),
        max(0.1, args.min_scene_interval),
        max(0.5, args.fallback_interval),
        warnings,
    )
    scenes = build_scenes(times, transcript_segments)
    keyframes = extract_keyframes(source, ffmpeg, scenes, duration, keyframes_dir, warnings)

    scenes_payload = {
        "method": "ffmpeg_scene_detect",
        "scene_threshold": args.scene_threshold,
        "min_scene_interval": args.min_scene_interval,
        "scene_count": len(scenes),
        "scenes": scenes,
    }
    scenes_path = analysis_dir / "scenes.json"
    write_json(scenes_path, scenes_payload)

    keyframes_index_path = keyframes_dir / "index.json"
    write_json(
        keyframes_index_path,
        {
            "count": len(keyframes),
            "frames": keyframes,
        },
    )

    contact_sheet_path = analysis_dir / "contact_sheet.jpg"
    build_contact_sheet(
        ffmpeg,
        keyframes,
        contact_sheet_path,
        columns=args.sheet_columns,
        thumb_width=args.sheet_thumb_width,
        warnings=warnings,
    )

    audio_events_path = analysis_dir / "audio_events.json"
    analyze_audio_events(source, ffmpeg, bool(metadata["normalized"].get("audio", {}).get("available")), audio_events_path, warnings)

    ocr_path = analysis_dir / "ocr.json"
    run_ocr(
        keyframes,
        ocr_path,
        mode=args.ocr,
        language=args.ocr_language,
        max_frames=args.ocr_max_frames,
        warnings=warnings,
    )

    analysis_manifest_path = analysis_dir / "analysis_manifest.json"
    edit_plan_template_path = write_edit_plan_template(output_dir, project_source, analysis_manifest_path)
    transcript_txt = analysis_dir / "transcript.txt"
    transcript_srt = analysis_dir / "transcript.srt"
    timeline_path = analysis_dir / "timeline.md"
    assets = {
        "metadata": str(metadata_path),
        "scenes": str(scenes_path),
        "transcript_txt": str(transcript_txt),
        "transcript_srt": str(transcript_srt),
        "contact_sheet": str(contact_sheet_path),
        "keyframes_index": str(keyframes_index_path),
        "audio_events": str(audio_events_path),
        "ocr": str(ocr_path),
    }
    write_timeline(timeline_path, source, metadata, scenes, keyframes, assets, warnings)

    manifest = {
        "job_id": f"bggg-readvideo-{int(time.time() * 1000)}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_sec": round(time.time() - started, 3),
        "skill_root": str(SKILL_ROOT),
        "project_dir": str(project_dir),
        "source_video": str(source),
        "project_source_video": str(project_source),
        "raw_dir": str(raw_dir),
        "analysis_dir": str(analysis_dir),
        "output_dir": str(output_dir),
        "assets": {
            **assets,
            "timeline": str(timeline_path),
            "analysis_manifest": str(analysis_manifest_path),
            "edit_plan_template": str(edit_plan_template_path),
        },
        "counts": {
            "scenes": len(scenes),
            "keyframes": len(keyframes),
            "transcript_segments": len(transcript_segments),
        },
        "transcript": {
            key: value
            for key, value in transcript.items()
            if key not in {"segments"}
        },
        "warnings": warnings,
    }
    write_json(analysis_manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
