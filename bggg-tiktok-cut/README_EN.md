# bggg-tiktok-cut

[中文](./README.md) | English

`bggg-tiktok-cut` is a local FFmpeg editing skill for turning AI videos, talking-head clips, product footage, or multiple source clips into publishable 9:16 TikTok/Reels/Shorts videos.

## Features

- Initialize a structured editing project with raw media, metadata, transcripts, plans, captions, and renders.
- Probe media with `ffprobe` and extract diagnostic frames.
- Optionally transcribe speech.
- Use a JSON edit plan for clips, reframing, captions, overlays, BGM, and export settings.
- Render a 1080x1920 MP4 with FFmpeg and write a render report.

## Install

```bash
mkdir -p ~/.codex/skills
cp -R bggg-tiktok-cut ~/.codex/skills/
brew install ffmpeg
```

Optionally install Whisper or faster-whisper for transcription.

## Usage

```bash
python3 bggg-tiktok-cut/scripts/init_project.py \
  bggg-tiktok-cut/projects/20260611_demo \
  --name demo \
  --inputs "/path/to/source.mp4"

python3 bggg-tiktok-cut/scripts/probe_media.py \
  bggg-tiktok-cut/projects/20260611_demo/raw \
  --out bggg-tiktok-cut/projects/20260611_demo/metadata/media_inventory.json \
  --frames-dir bggg-tiktok-cut/projects/20260611_demo/diagnostics/frames

python3 bggg-tiktok-cut/scripts/make_plan.py \
  bggg-tiktok-cut/projects/20260611_demo \
  --title "TikTok hook" \
  --target-seconds 30

python3 bggg-tiktok-cut/scripts/render_tiktok_cut.py \
  bggg-tiktok-cut/projects/20260611_demo/plans/edit_plan.json
```

## Safety

Keep run artifacts, rendered videos, subtitles, transcripts, and diagnostic frames under `projects/` or another local work directory. Do not commit them to the public repository.
