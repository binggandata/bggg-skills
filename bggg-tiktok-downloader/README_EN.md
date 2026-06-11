# bggg-tiktok-downloader

[中文](./README.md) | English

`bggg-tiktok-downloader` is a TikTok video download skill. It uses `yt-dlp` for single videos and visible creator posts, falls back to tikwm for single-video failures, and writes a `download_manifest.json` for downstream transcription or analysis.

## Install

```bash
mkdir -p ~/.codex/skills
cp -R bggg-tiktok-downloader ~/.codex/skills/
python3 -m pip install -U yt-dlp
brew install ffmpeg
```

Optional: if you have a local TikTokDownloader checkout, set:

```bash
export TIKTOKDOWNLOADER_ROOT="/path/to/TikTokDownloader"
```

It is only used for URL classification helpers and is not required.

## Usage

Download one video:

```bash
python3 bggg-tiktok-downloader/scripts/download_tiktok.py \
  "https://www.tiktok.com/@user/video/1234567890123456789" \
  --thumbnail
```

Download the latest 30 visible posts from a creator:

```bash
python3 bggg-tiktok-downloader/scripts/download_tiktok.py \
  "https://www.tiktok.com/@user" \
  --mode author \
  --limit 30 \
  --thumbnail
```

Default output directory:

```text
bggg-tiktok-downloader/projects/downloads/tiktok/
```

## Safety

Only download content you are allowed to save and process. When login state is required, pass `--cookies-browser chrome` or `--cookies-file` explicitly, but do not commit cookie files, browser profiles, downloaded videos, or `.info.json` files.
