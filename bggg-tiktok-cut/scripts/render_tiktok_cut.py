#!/usr/bin/env python3
"""Render a TikTok-ready vertical cut from a JSON edit plan.

The renderer intentionally keeps the creative decisions in the plan and makes
the mechanical parts deterministic: per-clip normalization, safe-zone captions,
BGM mix, optional watermark, and final 1080x1920 export.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from pathlib import Path

from media_common import atempo_chain, media_info, require_binary, run


GRADE_FILTERS = {
    "none": "",
    "neutral": "eq=contrast=1.03:saturation=1.02",
    "punch": "eq=contrast=1.08:saturation=1.12:gamma=1.0,unsharp=5:5:0.35:3:3:0.12",
    "warm": "eq=contrast=1.06:saturation=1.08:gamma_r=1.03:gamma_b=0.97",
    "soft": "eq=contrast=0.98:saturation=0.96,unsharp=3:3:0.18",
}


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def resolve_project_root(plan_path: Path, explicit: Path | None) -> Path:
    if explicit:
        return explicit.expanduser().resolve()
    if plan_path.parent.name == "plans":
        return plan_path.parent.parent.resolve()
    return plan_path.parent.resolve()


def resolve_path(value: str | None, project_root: Path) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h}:{m:02d}:{s:05.2f}"


def ass_escape(text: str) -> str:
    return (
        str(text)
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\r\n", "\n")
        .replace("\n", "\\N")
    )


def ffmpeg_filter_path(path: Path) -> str:
    text = str(path.resolve())
    return text.replace("\\", "\\\\").replace("'", "\\'")


def is_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def wrap_caption(text: str, max_chars: int = 18) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if not text:
        return ""
    if "\\N" in text or "\n" in text:
        return text.replace("\n", "\\N")
    if is_cjk(text):
        chunks = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
        return "\\N".join(chunks[:2])
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if len(candidate) > max_chars and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return "\\N".join(lines[:2])


def parse_srt_timestamp(value: str) -> float:
    hms, ms = value.strip().replace(".", ",").split(",", 1)
    h, m, s = [int(part) for part in hms.split(":")]
    return h * 3600 + m * 60 + s + int(ms[:3].ljust(3, "0")) / 1000


def parse_srt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\s*\n", text.strip())
    captions: list[dict] = []
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if re.fullmatch(r"\d+", lines[0]):
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        start_s, end_s = [part.strip() for part in lines[0].split("-->", 1)]
        captions.append(
            {
                "start": parse_srt_timestamp(start_s),
                "end": parse_srt_timestamp(end_s),
                "text": " ".join(lines[1:]).strip(),
            }
        )
    return captions


def grade_filter(name_or_filter: str | None) -> str:
    if not name_or_filter:
        return GRADE_FILTERS["punch"]
    return GRADE_FILTERS.get(name_or_filter, name_or_filter)


def crop_anchor(anchor: str) -> tuple[str, str]:
    anchor = (anchor or "center").lower()
    if "left" in anchor:
        x = "0"
    elif "right" in anchor:
        x = "iw-ow"
    else:
        x = "(iw-ow)/2"
    if "top" in anchor:
        y = "0"
    elif "bottom" in anchor:
        y = "ih-oh"
    else:
        y = "(ih-oh)/2"
    return x, y


def video_fit_filter(width: int, height: int, fit: str, anchor: str) -> str:
    fit = (fit or "blur-bg").lower()
    x, y = crop_anchor(anchor)
    cover = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}:{x}:{y},setsar=1"
    )
    contain = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    )
    if fit == "cover":
        return cover
    if fit == "contain":
        return contain
    if fit == "blur-bg":
        fg = f"scale={width}:{height}:force_original_aspect_ratio=decrease,setsar=1"
        return (
            f"split=2[vbg][vfg];"
            f"[vbg]{cover},gblur=sigma=32,eq=saturation=0.82:brightness=-0.04[bg];"
            f"[vfg]{fg}[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2:format=auto,setsar=1"
        )
    raise SystemExit(f"Unknown fit mode '{fit}'. Use cover, contain, or blur-bg.")


def normalize_clips(plan: dict) -> list[dict]:
    clips = plan.get("clips") or []
    if not clips:
        raise SystemExit("Plan has no clips.")
    normalized: list[dict] = []
    output_cursor = 0.0
    for index, clip in enumerate(clips):
        start = float(clip.get("start", 0.0))
        end = float(clip.get("end", 0.0))
        if end <= start:
            raise SystemExit(f"Clip #{index + 1} has invalid start/end: {start} -> {end}")
        speed = float(clip.get("speed", 1.0))
        if speed <= 0:
            raise SystemExit(f"Clip #{index + 1} speed must be positive.")
        input_duration = end - start
        output_duration = input_duration / speed
        item = dict(clip)
        item.update(
            {
                "index": index,
                "start": start,
                "end": end,
                "speed": speed,
                "input_duration": input_duration,
                "output_start": output_cursor,
                "output_end": output_cursor + output_duration,
                "output_duration": output_duration,
            }
        )
        normalized.append(item)
        output_cursor += output_duration
    return normalized


def render_segment(
    clip: dict,
    source_path: Path,
    out_path: Path,
    target: dict,
    defaults: dict,
    export: dict,
    source_info: dict,
) -> None:
    width = int(target.get("width", 1080))
    height = int(target.get("height", 1920))
    fps = int(target.get("fps", 30))
    fit = clip.get("fit") or defaults.get("fit") or "blur-bg"
    anchor = clip.get("anchor") or defaults.get("anchor") or "center"
    speed = float(clip["speed"])
    output_duration = float(clip["output_duration"])
    fade = min(0.03, max(0.0, output_duration / 4))

    vf = video_fit_filter(width, height, fit, anchor)
    g = grade_filter(clip.get("grade") or defaults.get("grade"))
    if g:
        vf = f"{vf},{g}"
    vf = f"[0:v]setpts=PTS-STARTPTS,setpts=PTS/{speed:.8f},{vf},fps={fps},format=yuv420p[vout]"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{float(clip['start']):.3f}",
        "-i",
        str(source_path),
        "-t",
        f"{float(clip['input_duration']):.3f}",
    ]

    audio_source_label = "0:a"
    if not source_info.get("has_audio"):
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-t",
                f"{output_duration:.3f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]
        )
        audio_source_label = "1:a"

    audio_filters = [f"[{audio_source_label}]asetpts=PTS-STARTPTS"]
    tempo = atempo_chain(speed)
    if tempo:
        audio_filters.append(tempo)
    clip_volume = float(clip.get("volume", defaults.get("voice_volume", 1.0)))
    audio_filters.append(f"volume={clip_volume:.4f}")
    if fade > 0:
        fade_out_start = max(0.0, output_duration - fade)
        audio_filters.append(f"afade=t=in:st=0:d={fade:.3f}")
        audio_filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={fade:.3f}")
    audio_filters.append("aresample=48000")
    audio_filters.append("aformat=channel_layouts=stereo")
    af = ",".join(audio_filters) + "[aout]"
    filter_complex = f"{vf};{af}"

    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            str(export.get("preset", "fast")),
            "-crf",
            str(export.get("crf", 20)),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            str(export.get("audio_bitrate", "192k")),
            "-ar",
            "48000",
            "-shortest",
            str(out_path),
        ]
    )
    run(cmd)


def concat_segments(paths: list[Path], out_path: Path, work_dir: Path) -> None:
    list_path = work_dir / "concat.txt"
    list_path.write_text("".join(f"file '{path.resolve()}'\n" for path in paths), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(out_path)])


def style_for_event(event: dict, fallback: str) -> str:
    style = (event.get("style") or fallback or "caption").lower()
    if style in {"hook", "top", "headline"}:
        return "Hook"
    if style in {"badge", "center"}:
        return "Badge"
    if style in {"minimal", "clean"}:
        return "Minimal"
    return "Caption"


def collect_caption_events(plan: dict, clips: list[dict], project_root: Path) -> list[dict]:
    events: list[dict] = []
    captions_file = resolve_path(plan.get("captions_file"), project_root)
    if captions_file and captions_file.exists():
        events.extend(parse_srt(captions_file))
    events.extend(plan.get("captions") or [])

    for clip in clips:
        if clip.get("caption"):
            events.append(
                {
                    "start": clip["output_start"],
                    "end": min(clip["output_end"], clip["output_start"] + 4.0),
                    "text": clip["caption"],
                    "style": clip.get("caption_style", "tiktok-bold"),
                }
            )

    overlays = []
    for overlay in plan.get("overlays") or []:
        item = dict(overlay)
        item.setdefault("style", "hook")
        overlays.append(item)
    events.extend(overlays)
    return events


def write_ass(plan: dict, clips: list[dict], project_root: Path, out_path: Path, total_duration: float) -> Path | None:
    settings = plan.get("settings") or {}
    events = collect_caption_events(plan, clips, project_root)
    events = [e for e in events if e.get("text") and float(e.get("end", 0)) > float(e.get("start", 0))]
    if not events:
        return None

    target = (plan.get("project") or {}).get("target") or {}
    width = int(target.get("width", 1080))
    height = int(target.get("height", 1920))
    font = settings.get("font", "Arial")
    caption_size = int(settings.get("caption_font_size", 86))
    hook_size = int(settings.get("hook_font_size", 92))
    margin_lr = 70
    caption_margin = int(height * 0.30)
    hook_margin = int(height * 0.08)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{caption_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,2,2,{margin_lr},{margin_lr},{caption_margin},1
Style: Hook,{font},{hook_size},&H0000FFFF,&H00FFFFFF,&H00000000,&H8A000000,1,0,0,0,100,100,0,0,1,8,2,8,{margin_lr},{margin_lr},{hook_margin},1
Style: Badge,{font},{int(caption_size * 0.85)},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,3,8,0,5,{margin_lr},{margin_lr},0,1
Style: Minimal,{font},{int(caption_size * 0.72)},&H00FFFFFF,&H000000FF,&H66000000,&H00000000,0,0,0,0,100,100,0,0,1,3,1,2,{margin_lr},{margin_lr},{caption_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    default_style = settings.get("caption_style", "tiktok-bold")
    for event in events:
        start = max(0.0, float(event.get("start", 0.0)))
        end = min(total_duration, float(event.get("end", 0.0)))
        if end <= start:
            continue
        style = style_for_event(event, default_style)
        text = wrap_caption(str(event["text"]), int(event.get("max_chars", 18)))
        effect = ""
        if style in {"Hook", "Badge"}:
            effect = r"{\fad(120,120)}"
        lines.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{effect}{ass_escape(text)}"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def watermark_overlay(position: str, margin: int) -> tuple[str, str]:
    position = (position or "top-right").lower()
    if "left" in position:
        x = str(margin)
    elif "right" in position:
        x = f"W-w-{margin}"
    else:
        x = "(W-w)/2"
    if "bottom" in position:
        y = f"H-h-{margin}"
    elif "top" in position:
        y = str(margin)
    else:
        y = "(H-h)/2"
    return x, y


def final_render(
    base_path: Path,
    ass_path: Path | None,
    plan: dict,
    project_root: Path,
    out_path: Path,
    total_duration: float,
) -> None:
    export = plan.get("export") or {}
    settings = plan.get("settings") or {}
    cmd = ["ffmpeg", "-y", "-i", str(base_path)]
    filter_parts: list[str] = []
    video_label = "[0:v]"
    next_input = 1

    bgm = plan.get("bgm") or {}
    bgm_path = resolve_path(bgm.get("path"), project_root)
    if bgm_path:
        if not bgm_path.exists():
            raise SystemExit(f"BGM file not found: {bgm_path}")
        cmd.extend(["-stream_loop", "-1", "-i", str(bgm_path)])
        next_input += 1

    watermark = plan.get("watermark") or {}
    watermark_path = resolve_path(watermark.get("path"), project_root)
    if watermark_path:
        if not watermark_path.exists():
            raise SystemExit(f"Watermark file not found: {watermark_path}")
        cmd.extend(["-loop", "1", "-i", str(watermark_path)])
        wm_index = next_input
        next_input += 1
        wm_width = int(watermark.get("width", 180))
        opacity = float(watermark.get("opacity", 0.85))
        margin = int(watermark.get("margin", 48))
        x, y = watermark_overlay(watermark.get("position", "top-right"), margin)
        filter_parts.append(
            f"[{wm_index}:v]format=rgba,scale={wm_width}:-1,colorchannelmixer=aa={opacity:.3f}[wm];"
            f"{video_label}[wm]overlay={x}:{y}:format=auto[vwm]"
        )
        video_label = "[vwm]"

    if ass_path:
        filter_parts.append(f"{video_label}subtitles=filename='{ffmpeg_filter_path(ass_path)}'[vout]")
    else:
        filter_parts.append(f"{video_label}null[vout]")

    voice_volume = float(settings.get("voice_volume", 1.0))
    if bgm_path:
        bgm_volume = float(bgm.get("volume", 0.12))
        bgm_start = float(bgm.get("start", 0.0))
        fade_in = max(0.0, float(bgm.get("fade_in", 0.3)))
        fade_out = max(0.0, float(bgm.get("fade_out", 0.8)))
        fade_out_start = max(0.0, total_duration - fade_out)
        filter_parts.append(f"[0:a]volume={voice_volume:.4f},aresample=48000[a0]")
        filter_parts.append(
            f"[1:a]atrim=start={bgm_start:.3f}:duration={total_duration:.3f},"
            f"asetpts=PTS-STARTPTS,volume={bgm_volume:.4f},"
            f"afade=t=in:st=0:d={fade_in:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f},"
            f"aresample=48000,aformat=channel_layouts=stereo[a1]"
        )
        filter_parts.append("[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]")
    else:
        filter_parts.append(f"[0:a]volume={voice_volume:.4f},aresample=48000,aformat=channel_layouts=stereo[aout]")

    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            str(export.get("preset", "fast")),
            "-crf",
            str(export.get("crf", 20)),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            str(export.get("audio_bitrate", "192k")),
            "-t",
            f"{total_duration:.3f}",
        ]
    )
    if export.get("faststart", True):
        cmd.extend(["-movflags", "+faststart"])
    cmd.append(str(out_path))
    run(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a TikTok-ready cut from an edit plan.")
    parser.add_argument("plan", type=Path, help="Path to edit_plan.json.")
    parser.add_argument("--project-root", type=Path, help="Project root. Defaults to parent of plans/.")
    parser.add_argument("--output", type=Path, help="Output mp4 path.")
    parser.add_argument("--keep-work", action="store_true", help="Keep normalized segment files.")
    args = parser.parse_args()

    require_binary("ffmpeg")
    require_binary("ffprobe")

    plan_path = args.plan.expanduser().resolve()
    plan = load_json(plan_path)
    project_root = resolve_project_root(plan_path, args.project_root)
    renders_dir = project_root / "renders"
    work_dir = renders_dir / "_work"
    segments_dir = work_dir / "segments"
    renders_dir.mkdir(parents=True, exist_ok=True)
    segments_dir.mkdir(parents=True, exist_ok=True)

    project = plan.get("project") or {}
    target = project.get("target") or {"width": 1080, "height": 1920, "fps": 30}
    defaults = plan.get("settings") or {}
    export = plan.get("export") or {}
    clips = normalize_clips(plan)

    segment_paths: list[Path] = []
    report_clips: list[dict] = []
    source_cache: dict[str, dict] = {}
    for clip in clips:
        source_path = resolve_path(str(clip.get("source", "")), project_root)
        if not source_path or not source_path.exists():
            raise SystemExit(f"Clip source not found: {clip.get('source')}")
        cache_key = str(source_path)
        if cache_key not in source_cache:
            source_cache[cache_key] = media_info(source_path)
        out_path = segments_dir / f"seg_{clip['index']:03d}_{source_path.stem}.mp4"
        render_segment(clip, source_path, out_path, target, defaults, export, source_cache[cache_key])
        segment_paths.append(out_path)
        report_clips.append(
            {
                "source": str(source_path),
                "start": clip["start"],
                "end": clip["end"],
                "speed": clip["speed"],
                "output_start": round(clip["output_start"], 3),
                "output_end": round(clip["output_end"], 3),
                "label": clip.get("label"),
            }
        )

    total_duration = sum(float(c["output_duration"]) for c in clips)
    base_path = work_dir / "base_concat.mp4"
    concat_segments(segment_paths, base_path, work_dir)

    ass_path = write_ass(plan, clips, project_root, project_root / "captions" / "final_captions.ass", total_duration)
    output_name = defaults.get("output_name", "final_tiktok.mp4")
    out_path = args.output.expanduser().resolve() if args.output else renders_dir / output_name
    final_render(base_path, ass_path, plan, project_root, out_path, total_duration)

    info = media_info(out_path)
    report = {
        "plan": str(plan_path),
        "project_root": str(project_root),
        "output": str(out_path),
        "duration": round(total_duration, 3),
        "media_info": info,
        "clips": report_clips,
        "captions": str(ass_path) if ass_path else None,
    }
    (renders_dir / "render_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if not args.keep_work:
        shutil.rmtree(segments_dir, ignore_errors=True)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
