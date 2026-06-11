# bggg-tiktok-readvideo

[中文](./README.md) | English

`bggg-tiktok-readvideo` is a local Codex skill that helps Codex understand videos by turning them into structured context instead of pretending the model can directly watch an MP4. It extracts metadata, transcript, scenes, keyframes, a contact sheet, audio events, optional OCR, and a readable timeline so Codex can reason over timestamps and create TikTok edit plans.

## Features

- Analyze local `.mp4/.mov/.webm/.mkv` videos.
- Generate `metadata.json` with `ffprobe`.
- Detect scene changes and extract keyframes with `ffmpeg`.
- Create labeled `keyframes/` and `contact_sheet.jpg`.
- Optionally transcribe audio with local `whisper-cli` or `whisper-cpp`.
- Run standalone batch transcription for video/audio folders, writing `transcripts/` and `transcription_manifest.json`.
- Optionally OCR keyframes with `tesseract`.
- Generate `timeline.md` and `analysis_manifest.json` for Codex.
- Render a 9:16 TikTok output from `edit_plan.json`.

## Install

Copy the skill into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R bggg-tiktok-readvideo ~/.codex/skills/
```

Or symlink it during development:

```bash
ln -s "$PWD/bggg-tiktok-readvideo" ~/.codex/skills/bggg-tiktok-readvideo
```

Required system dependency:

```bash
brew install ffmpeg
```

Optional dependencies:

```bash
brew install whisper-cpp tesseract
```

The script automatically searches common user-level NGSpilot and whisper.cpp model folders. You can also pass `--model /path/to/ggml-small.bin`.

## Usage

Analyze a video:

```bash
python3 bggg-tiktok-readvideo/scripts/analyze_video.py "/path/to/input.mp4" \
  --slug product_qc_ugc
```

Transcribe audio only:

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/video-or-folder" --recursive --srt
```

Project output:

```text
bggg-tiktok-readvideo/projects/YYYYMMDD_product_qc_ugc/
├── raw/input.mp4
├── analysis/
│   ├── metadata.json
│   ├── transcript.txt
│   ├── transcript.srt
│   ├── scenes.json
│   ├── timeline.md
│   ├── contact_sheet.jpg
│   ├── keyframes/
│   ├── audio_events.json
│   ├── ocr.json
│   └── analysis_manifest.json
└── output/
    └── edit_plan.template.json
```

Example Codex prompt:

```text
Use bggg-tiktok-readvideo to analyze this video. Read timeline.md,
scenes.json, transcript.srt, and contact_sheet.jpg. Find the best TikTok
hook, proof shots, and CTA, then create output/edit_plan.json.
```

Render:

```bash
python3 bggg-tiktok-readvideo/scripts/render_tiktok.py \
  bggg-tiktok-readvideo/projects/YYYYMMDD_product_qc_ugc/output/edit_plan.json
```

## Batch Transcription

The standalone transcription workflow from `bggg-tiktok-whisper` has been merged into this skill. Use it when the user needs ASR/subtitles but does not need keyframes or a timeline:

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/downloads" --recursive
```

By default, outputs are written to a `transcripts/` directory beside each source file. Pass `--output-dir` to collect results in one folder. Existing `.txt` files are skipped unless `--force` is set. Supported options include `--model small`, `--language auto`, `--srt`, and `--json`.

## References

These video-understanding projects were studied while designing the skill:

- Popcorn
- video-understanding-engine
- video-understanding-local
- video-analyzer

They are not vendored in the open-source skill and are not runtime dependencies. This skill's runtime is self-contained and does not import them. See `references/source-projects.md` for the design notes.

## License

MIT
