#!/usr/bin/env python3
"""Probe media and optionally export diagnostic frames for editing decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from media_common import list_media_files, media_info, require_binary, run, seconds_at_percent


def sample_frames(video: Path, info: dict, out_dir: Path, count: int) -> list[str]:
    if not info.get("has_video") or count <= 0:
        return []
    require_binary("ffmpeg")
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = float(info.get("duration") or 0)
    if count == 1:
        percents = [0.5]
    else:
        percents = [0.08 + (0.84 * i / (count - 1)) for i in range(count)]
    outputs: list[str] = []
    for index, pct in enumerate(percents, 1):
        ts = seconds_at_percent(duration, pct)
        out = out_dir / f"{video.stem}_{index:02d}_{ts:.2f}s.jpg"
        run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-update",
                "1",
                str(out),
            ],
            quiet=True,
        )
        outputs.append(str(out))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe video/audio/image files for a TikTok edit.")
    parser.add_argument("paths", nargs="+", type=Path, help="Media files or directories.")
    parser.add_argument("--out", type=Path, help="Write JSON inventory to this path.")
    parser.add_argument("--frames-dir", type=Path, help="Export diagnostic JPG frames here.")
    parser.add_argument("--sample-count", type=int, default=5, help="Frames per video when --frames-dir is set.")
    args = parser.parse_args()

    files: list[Path] = []
    for path in args.paths:
        files.extend(list_media_files(path.expanduser()))
    if not files:
        raise SystemExit("No media files found.")

    inventory = {"files": [], "summary": {"count": len(files), "total_duration": 0.0}}
    for file_path in files:
        info = media_info(file_path)
        inventory["summary"]["total_duration"] += float(info.get("duration") or 0)
        if args.frames_dir and info.get("has_video"):
            frame_dir = args.frames_dir.expanduser().resolve() / file_path.stem
            info["diagnostic_frames"] = sample_frames(file_path, info, frame_dir, args.sample_count)
        inventory["files"].append(info)
    inventory["summary"]["total_duration"] = round(inventory["summary"]["total_duration"], 3)

    text = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        args.out.expanduser().resolve().write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
