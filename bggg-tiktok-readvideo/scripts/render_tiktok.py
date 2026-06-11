#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence


def run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def resolve_command(explicit: str, candidates: Sequence[str]) -> str:
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return str(path)
        found = shutil.which(explicit)
        if found:
            return found
        raise SystemExit(f"Command not found: {explicit}")
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
        path = Path(candidate).expanduser()
        if path.exists():
            return str(path)
    raise SystemExit(f"Command not found. Install one of: {', '.join(candidates)}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def normalize_segments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        start = float(item.get("start", 0))
        end = float(item.get("end", 0))
        if end <= start:
            raise SystemExit(f"Invalid segment {index}: end must be greater than start")
        segments.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "duration": end - start,
                "label": item.get("label", f"segment_{index}"),
                "reason": item.get("reason", ""),
            }
        )
    if not segments:
        raise SystemExit("edit_plan.json has no segments.")
    return segments


def build_video_filter(width: int, height: int, fps: int, fit: str) -> str:
    if fit == "contain":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"fps={fps},setsar=1"
        )
    return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps},setsar=1"


def render_segment(ffmpeg: str, source: Path, segment: dict[str, Any], target: Path, vf: str) -> None:
    result = run_command(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{segment['start']:.3f}",
            "-to",
            f"{segment['end']:.3f}",
            "-i",
            str(source),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffmpeg failed for segment {segment['index']}")


def concat_segments(ffmpeg: str, clips: list[Path], target: Path, temp_dir: Path) -> None:
    concat_file = temp_dir / "concat.txt"
    lines = []
    for path in clips:
        escaped = str(path).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = run_command(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(target),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg concat failed")


def caption_intersections(
    captions: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    *,
    source_timeline: bool,
) -> list[dict[str, Any]]:
    if not captions:
        return []
    if not source_timeline:
        return [
            {
                "start": float(item.get("start", 0)),
                "end": float(item.get("end", 0)),
                "text": str(item.get("text", "")).strip(),
            }
            for item in captions
            if str(item.get("text", "")).strip()
        ]

    output: list[dict[str, Any]] = []
    cursor = 0.0
    for segment in segments:
        seg_start = segment["start"]
        seg_end = segment["end"]
        for caption in captions:
            cap_start = float(caption.get("start", 0))
            cap_end = float(caption.get("end", cap_start))
            text = str(caption.get("text", "")).strip()
            if not text:
                continue
            start = max(seg_start, cap_start)
            end = min(seg_end, cap_end)
            if end <= start:
                continue
            output.append(
                {
                    "start": cursor + (start - seg_start),
                    "end": cursor + (end - seg_start),
                    "text": text,
                }
            )
        cursor += segment["duration"]
    return output


def write_srt(captions: list[dict[str, Any]], path: Path) -> None:
    lines: list[str] = []
    index = 1
    for item in captions:
        start = float(item["start"])
        end = float(item["end"])
        text = str(item["text"]).strip()
        if not text or end <= start:
            continue
        lines.extend([str(index), f"{seconds_to_srt(start)} --> {seconds_to_srt(end)}", text, ""])
        index += 1
    path.write_text("\n".join(lines), encoding="utf-8")


def escape_filter_path(path: Path) -> str:
    value = str(path)
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def burn_subtitles(ffmpeg: str, source: Path, srt_path: Path, output: Path, style: str) -> None:
    filter_value = f"subtitles='{escape_filter_path(srt_path)}':force_style='{style}'"
    result = run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vf",
            filter_value,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "subtitle burn failed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a 9:16 TikTok video from bggg-tiktok-readvideo edit_plan.json.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("edit_plan", help="Path to edit_plan.json.")
    parser.add_argument("--ffmpeg", default="", help="ffmpeg path.")
    parser.add_argument("--output", default="", help="Override output path.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print render plan without writing video.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan_path = Path(args.edit_plan).expanduser().resolve()
    plan = load_json(plan_path)
    defaults = plan.get("defaults") if isinstance(plan.get("defaults"), dict) else {}
    source = Path(str(plan.get("source_video", ""))).expanduser()
    if not source.is_absolute():
        source = (plan_path.parent / source).resolve()
    else:
        source = source.resolve()
    if not source.exists():
        raise SystemExit(f"source_video not found: {source}")

    segments = normalize_segments(plan.get("segments", []))
    width = int(defaults.get("width", 1080))
    height = int(defaults.get("height", 1920))
    fps = int(defaults.get("fps", 30))
    fit = str(defaults.get("fit", "cover"))
    burn = bool(defaults.get("burn_captions", True))
    source_timeline = bool(defaults.get("caption_source_timeline", True))
    output = Path(args.output or plan.get("output") or plan_path.parent / "final_tiktok_9x16.mp4").expanduser()
    if not output.is_absolute():
        output = (plan_path.parent / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = resolve_command(args.ffmpeg, ["ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"])
    video_filter = build_video_filter(width, height, fps, fit)

    summary = {
        "source_video": str(source),
        "output": str(output),
        "segment_count": len(segments),
        "duration_sec": round(sum(item["duration"] for item in segments), 3),
        "width": width,
        "height": height,
        "fps": fps,
        "fit": fit,
        "burn_captions": burn,
    }
    if args.dry_run:
        print(json.dumps({"summary": summary, "segments": segments}, ensure_ascii=False, indent=2))
        return 0

    with tempfile.TemporaryDirectory(prefix="bggg-tiktok-render-") as temp:
        temp_dir = Path(temp)
        clips: list[Path] = []
        for segment in segments:
            target = temp_dir / f"clip_{segment['index']:04d}.mp4"
            render_segment(ffmpeg, source, segment, target, video_filter)
            clips.append(target)

        concat_output = temp_dir / "concat.mp4"
        concat_segments(ffmpeg, clips, concat_output, temp_dir)

        captions = caption_intersections(plan.get("captions", []), segments, source_timeline=source_timeline)
        if burn and captions:
            srt_path = temp_dir / "captions.srt"
            write_srt(captions, srt_path)
            style = str(
                defaults.get(
                    "subtitle_style",
                    "FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "BorderStyle=3,BackColour=&H99000000,Outline=1,Shadow=0,Alignment=2,MarginV=180",
                )
            )
            burn_subtitles(ffmpeg, concat_output, srt_path, output, style)
        else:
            shutil.copy2(concat_output, output)

    summary_path = output.with_suffix(".render_summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**summary, "summary_path": str(summary_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
