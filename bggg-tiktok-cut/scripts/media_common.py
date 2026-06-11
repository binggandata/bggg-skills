#!/usr/bin/env python3
"""Shared helpers for bggg-tiktok-cut scripts."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path


VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def run(cmd: list[str], *, capture: bool = False, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    if not quiet:
        preview = " ".join(str(part) for part in cmd[:10])
        if len(cmd) > 10:
            preview += " ..."
        print(f"$ {preview}", file=sys.stderr)
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        capture_output=capture,
    )


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Missing required binary: {name}. Install it and retry.")


def slugify(value: str, fallback: str = "tiktok-cut") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or fallback


def ffprobe_json(path: Path) -> dict:
    require_binary("ffprobe")
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format:stream",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
        quiet=True,
    )
    return json.loads(result.stdout)


def parse_rate(rate: str | None) -> float | None:
    if not rate or rate == "0/0":
        return None
    if "/" in rate:
        num, den = rate.split("/", 1)
        try:
            den_f = float(den)
            if den_f == 0:
                return None
            return float(num) / den_f
        except ValueError:
            return None
    try:
        return float(rate)
    except ValueError:
        return None


def media_info(path: Path) -> dict:
    path = path.resolve()
    data = ffprobe_json(path)
    streams = data.get("streams", [])
    v_streams = [s for s in streams if s.get("codec_type") == "video"]
    a_streams = [s for s in streams if s.get("codec_type") == "audio"]
    fmt = data.get("format", {})
    duration = fmt.get("duration")
    if duration is None and v_streams:
        duration = v_streams[0].get("duration")
    try:
        duration_f = float(duration) if duration is not None else 0.0
    except ValueError:
        duration_f = 0.0

    video = v_streams[0] if v_streams else {}
    fps = parse_rate(video.get("avg_frame_rate")) or parse_rate(video.get("r_frame_rate"))
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    rotation = video.get("rotation")
    if rotation is None:
        for side in video.get("side_data_list", []) or []:
            if "rotation" in side:
                rotation = side.get("rotation")
                break

    return {
        "path": str(path),
        "name": path.name,
        "suffix": path.suffix.lower(),
        "duration": round(duration_f, 3),
        "width": width,
        "height": height,
        "fps": round(fps, 3) if fps else None,
        "has_video": bool(v_streams),
        "has_audio": bool(a_streams),
        "video_codec": video.get("codec_name"),
        "audio_codec": a_streams[0].get("codec_name") if a_streams else None,
        "color_transfer": video.get("color_transfer"),
        "pix_fmt": video.get("pix_fmt"),
        "rotation": rotation,
        "aspect_ratio": round(width / height, 4) if width and height else None,
        "bit_rate": int(fmt.get("bit_rate")) if str(fmt.get("bit_rate", "")).isdigit() else None,
    }


def list_media_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files: list[Path] = []
    for child in sorted(path.rglob("*")):
        if child.is_file() and child.suffix.lower() in VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS:
            files.append(child)
    return files


def seconds_at_percent(duration: float, percent: float) -> float:
    if duration <= 0:
        return 0.0
    return max(0.0, min(duration - 0.1, duration * percent))


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def atempo_chain(speed: float) -> str:
    """Build an ffmpeg atempo chain. atempo supports 0.5..100 in FFmpeg 8,
    but the 0.5..2.0 chain remains portable across older installs."""
    if math.isclose(speed, 1.0, rel_tol=0.001):
        return ""
    if speed <= 0:
        raise ValueError("speed must be positive")
    factors: list[float] = []
    remaining = speed
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={f:.6g}" for f in factors)
