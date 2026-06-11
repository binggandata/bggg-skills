#!/usr/bin/env python3
"""Create a clean TikTok cut project folder."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from media_common import VIDEO_EXTS, AUDIO_EXTS, IMAGE_EXTS, media_info, slugify


DEFAULT_PLAN = {
    "version": 1,
    "project": {
        "title": "TikTok cut",
        "platform": "tiktok",
        "target": {"width": 1080, "height": 1920, "fps": 30},
        "notes": "Replace the clips, captions, overlays, and bgm fields before rendering.",
    },
    "settings": {
        "fit": "blur-bg",
        "grade": "punch",
        "caption_style": "tiktok-bold",
        "caption_safe_zone": "middle",
        "voice_volume": 1.0,
        "output_name": "final_tiktok.mp4",
    },
    "clips": [
        {
            "source": "raw/example.mp4",
            "start": 0.0,
            "end": 5.0,
            "speed": 1.0,
            "fit": "blur-bg",
            "anchor": "center",
            "label": "HOOK",
        }
    ],
    "captions": [
        {"start": 0.0, "end": 2.0, "text": "替换成大字字幕", "style": "tiktok-bold"}
    ],
    "overlays": [
        {"start": 0.0, "end": 2.2, "text": "3秒钩子", "position": "top", "style": "hook"}
    ],
    "bgm": {
        "path": "",
        "volume": 0.12,
        "start": 0.0,
        "fade_in": 0.3,
        "fade_out": 0.8,
    },
    "export": {
        "crf": 20,
        "preset": "fast",
        "audio_bitrate": "192k",
        "faststart": True,
    },
}


def copy_inputs(inputs: list[Path], project_dir: Path) -> list[dict]:
    copied: list[dict] = []
    raw_dir = project_dir / "raw"
    bgm_dir = project_dir / "assets" / "bgm"
    image_dir = project_dir / "assets" / "images"

    for src in inputs:
        src = src.expanduser().resolve()
        if not src.exists():
            raise SystemExit(f"Input not found: {src}")
        suffix = src.suffix.lower()
        if suffix in VIDEO_EXTS:
            dest_dir = raw_dir
        elif suffix in AUDIO_EXTS:
            dest_dir = bgm_dir
        elif suffix in IMAGE_EXTS:
            dest_dir = image_dir
        else:
            dest_dir = project_dir / "imports"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if dest.exists():
            stem = dest.stem
            counter = 2
            while dest.exists():
                dest = dest_dir / f"{stem}-{counter}{dest.suffix}"
                counter += 1
        shutil.copy2(src, dest)
        record = {"source": str(src), "copied_to": str(dest.relative_to(project_dir))}
        if suffix in VIDEO_EXTS | AUDIO_EXTS:
            try:
                record["media"] = media_info(dest)
            except Exception as exc:
                record["probe_error"] = str(exc)
        copied.append(record)
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a bggg-tiktok-cut project.")
    parser.add_argument("project_dir", type=Path, help="Destination project directory.")
    parser.add_argument("--name", help="Human-readable project name.")
    parser.add_argument("--inputs", nargs="*", type=Path, default=[], help="Files to copy into the project.")
    parser.add_argument("--force", action="store_true", help="Allow using an existing directory.")
    args = parser.parse_args()

    project_dir = args.project_dir.expanduser().resolve()
    if project_dir.exists() and any(project_dir.iterdir()) and not args.force:
        raise SystemExit(f"Project directory is not empty: {project_dir}. Use --force to reuse it.")

    for rel in [
        "raw",
        "audio",
        "transcripts",
        "plans",
        "captions",
        "assets/bgm",
        "assets/images",
        "assets/overlays",
        "renders",
        "diagnostics/frames",
        "metadata",
        "exports",
    ]:
        (project_dir / rel).mkdir(parents=True, exist_ok=True)

    title = args.name or project_dir.name
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    copied = copy_inputs(args.inputs, project_dir) if args.inputs else []

    manifest = {
        "name": title,
        "slug": slugify(title),
        "created_at": now,
        "project_dir": str(project_dir),
        "inputs": copied,
        "outputs": {
            "default_plan": "plans/edit_plan.template.json",
            "final": "renders/final_tiktok.mp4",
        },
    }
    (project_dir / "metadata" / "project.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    plan = dict(DEFAULT_PLAN)
    plan["project"] = dict(DEFAULT_PLAN["project"])
    plan["project"]["title"] = title
    if copied:
        video_inputs = [c for c in copied if c.get("copied_to", "").startswith("raw/")]
        if video_inputs:
            first = video_inputs[0]
            dur = first.get("media", {}).get("duration", 5.0)
            plan["clips"] = [
                {
                    "source": first["copied_to"],
                    "start": 0.0,
                    "end": min(float(dur or 5.0), 8.0),
                    "speed": 1.0,
                    "fit": "blur-bg",
                    "anchor": "center",
                    "label": "HOOK",
                }
            ]
    (project_dir / "plans" / "edit_plan.template.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
