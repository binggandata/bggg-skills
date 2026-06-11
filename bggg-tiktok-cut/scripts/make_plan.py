#!/usr/bin/env python3
"""Generate a conservative starter edit plan from a project folder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from media_common import VIDEO_EXTS, media_info


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a starter TikTok edit plan from raw videos.")
    parser.add_argument("project_dir", type=Path, help="Project directory created by init_project.py.")
    parser.add_argument("--title", default="TikTok cut", help="Title used for the hook overlay.")
    parser.add_argument("--target-seconds", type=float, default=30.0, help="Maximum output duration.")
    parser.add_argument("--each-max", type=float, default=8.0, help="Max seconds taken from each source clip.")
    parser.add_argument("--fit", default="blur-bg", choices=["blur-bg", "cover", "contain"])
    parser.add_argument("--grade", default="punch", choices=["none", "neutral", "punch", "warm", "soft"])
    parser.add_argument("--out", type=Path, help="Output plan path.")
    args = parser.parse_args()

    project_dir = args.project_dir.expanduser().resolve()
    raw_dir = project_dir / "raw"
    files = [p for p in sorted(raw_dir.glob("*")) if p.suffix.lower() in VIDEO_EXTS]
    if not files:
        raise SystemExit(f"No video files found in {raw_dir}")

    clips = []
    remaining = args.target_seconds
    for path in files:
        if remaining <= 0:
            break
        info = media_info(path)
        duration = float(info.get("duration") or 0)
        if duration <= 0:
            continue
        take = min(duration, args.each_max, remaining)
        clips.append(
            {
                "source": str(path.relative_to(project_dir)),
                "start": 0.0,
                "end": round(take, 3),
                "speed": 1.0,
                "fit": args.fit,
                "anchor": "center",
                "label": "BEAT",
            }
        )
        remaining -= take

    if not clips:
        raise SystemExit("No usable video clips found.")

    first_caption_end = min(2.8, sum(c["end"] - c["start"] for c in clips))
    plan = {
        "version": 1,
        "project": {
            "title": args.title,
            "platform": "tiktok",
            "target": {"width": 1080, "height": 1920, "fps": 30},
        },
        "settings": {
            "fit": args.fit,
            "grade": args.grade,
            "caption_style": "tiktok-bold",
            "voice_volume": 1.0,
            "output_name": "final_tiktok.mp4",
        },
        "clips": clips,
        "captions": [],
        "overlays": [
            {
                "start": 0.0,
                "end": round(first_caption_end, 3),
                "text": args.title,
                "position": "top",
                "style": "hook",
            }
        ],
        "bgm": {"path": "", "volume": 0.12, "start": 0.0, "fade_in": 0.3, "fade_out": 0.8},
        "export": {"crf": 20, "preset": "fast", "audio_bitrate": "192k", "faststart": True},
    }

    out_path = args.out.expanduser().resolve() if args.out else project_dir / "plans" / "edit_plan.auto.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"plan": str(out_path), "clips": len(clips)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
