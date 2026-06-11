---
name: bggg-tiktok-readvideo
description: >
  把 TikTok、Reels、YouTube Shorts、UGC 广告、本地 MP4/MOV/WebM 等视频拆成 Codex 可读的视频上下文。
  当用户要求 Codex 看懂视频、读视频、分析视频、总结视频、找 hook、找爆点、提取字幕、
  语音转文字、ASR、批量转写 TikTok 视频或音频、
  生成视频 timeline、抽关键帧、做 contact sheet、分析口播/画面/节奏、制定 TikTok 9:16 剪辑方案、
  或把原始视频素材变成 edit_plan.json 并用 FFmpeg 渲染短视频时，应该使用此 skill。
  本 skill 独立内置 ffprobe/ffmpeg/whisper.cpp/tesseract 可选流程，不依赖其他 BGGG skills。
---

# BGGG TikTok ReadVideo

这个 skill 的原则很简单：不要让 Codex 直接“看 mp4”。先把视频拆成可读、可搜索、可执行的上下文，再让 Codex 做判断、剪辑规划和渲染。

核心脚本：

```bash
python3 bggg-tiktok-readvideo/scripts/analyze_video.py "/path/to/input.mp4"
```

只需要转写音轨时使用独立转写脚本：

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/video-or-folder" --recursive --srt
```

脚本会创建：

```text
bggg-tiktok-readvideo/projects/YYYYMMDD_slug/
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

## Default Workflow

1. Run `scripts/analyze_video.py` before making any claim about the video content.
2. If the user only asks for transcription/ASR, run `scripts/transcribe_video.py` instead of the full visual analysis pipeline.
3. Read `analysis/timeline.md`, `analysis/scenes.json`, `analysis/transcript.srt`, `analysis/audio_events.json`, and `analysis/ocr.json`.
4. Inspect `analysis/contact_sheet.jpg` as the visual overview. Use individual `analysis/keyframes/frame_XXXX.jpg` when a scene needs closer visual reading.
5. If the user asks for TikTok editing, write `output/edit_plan.json` before rendering.
6. Render with `scripts/render_tiktok.py` only after the edit plan exists.

Do not infer content from the filename, title, or folder name alone. The timeline and contact sheet are the source of truth.

## Analyze Commands

Basic local analysis:

```bash
python3 bggg-tiktok-readvideo/scripts/analyze_video.py "/path/to/video.mp4"
```

Give the run a stable project name:

```bash
python3 bggg-tiktok-readvideo/scripts/analyze_video.py "/path/to/video.mp4" \
  --slug product_qc_ugc
```

Faster visual-only pass:

```bash
python3 bggg-tiktok-readvideo/scripts/analyze_video.py "/path/to/video.mp4" \
  --no-transcribe --max-frames 24
```

Use a specific whisper.cpp model:

```bash
python3 bggg-tiktok-readvideo/scripts/analyze_video.py "/path/to/video.mp4" \
  --model small --language auto
```

Scene detection tuning:

```bash
python3 bggg-tiktok-readvideo/scripts/analyze_video.py "/path/to/video.mp4" \
  --scene-threshold 0.22 --min-scene-interval 0.8 --max-frames 48
```

## Transcription Commands

The standalone transcription flow was merged from `bggg-tiktok-whisper`. It supports video/audio files, folders, recursive batch runs, skip-existing behavior, and a JSON manifest.

Transcribe one video or audio file:

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/video.mp4"
```

Batch transcribe a folder:

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/downloads" --recursive
```

Generate subtitles and JSON too:

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/video.mp4" --srt --json
```

Outputs default to a `transcripts/` folder beside the source file, or to `--output-dir` when provided. Existing `.txt` transcripts are skipped unless `--force` is set.

## Reading The Output

Use the artifacts in this order:

1. `analysis_manifest.json`: paths and warnings from the run.
2. `metadata.json`: duration, resolution, audio/video streams, fps, codec.
3. `contact_sheet.jpg`: quick visual pass across scenes.
4. `timeline.md`: scene table with transcript excerpts and keyframe paths.
5. `transcript.srt`: exact spoken-word timestamps.
6. `audio_events.json`: silence and volume clues for pacing.
7. `ocr.json`: screen text if `tesseract` is installed; otherwise it records why OCR was skipped.

When summarizing or editing, cite timestamps such as `00:03.20-00:06.80`.

## TikTok Edit Planning

For TikTok / UGC / ad editing, create `output/edit_plan.json` with this structure:

```json
{
  "source_video": "raw/input.mp4",
  "analysis_manifest": "analysis/analysis_manifest.json",
  "goal": "15-25s TikTok UGC edit for cross-border ecommerce",
  "output": "output/final_tiktok_9x16.mp4",
  "defaults": {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "fit": "cover",
    "burn_captions": true,
    "caption_source_timeline": true
  },
  "segments": [
    {
      "start": 0.0,
      "end": 2.2,
      "label": "hook",
      "reason": "Strong curiosity opening"
    }
  ],
  "captions": [
    {
      "start": 0.0,
      "end": 2.2,
      "text": "I found the cheaper way to buy this"
    }
  ]
}
```

TikTok defaults:

- 9:16, `1080x1920`, 30fps.
- Strong first 2 seconds.
- Remove dead air and repeated setup.
- Prefer proof shots: product close-up, QC photo, order screen, warehouse/packing, delivery proof.
- Keep captions short and readable; use the original language unless the user asks for translation.
- For cross-border ecommerce, look for trust points: QC, warehouse inspection, PayPal, tracking, shipping speed, real product comparison, price proof.

Render:

```bash
python3 bggg-tiktok-readvideo/scripts/render_tiktok.py \
  bggg-tiktok-readvideo/projects/YYYYMMDD_slug/output/edit_plan.json
```

Validate without rendering:

```bash
python3 bggg-tiktok-readvideo/scripts/render_tiktok.py \
  bggg-tiktok-readvideo/projects/YYYYMMDD_slug/output/edit_plan.json --dry-run
```

## What Codex Should Decide

The script extracts context; Codex still owns judgment:

- Which scene is the strongest hook.
- Which claim needs visual proof.
- Which silent or low-value spans to remove.
- Where B-roll should support the transcript.
- Whether the output should be summary, edit plan, final rendered video, or reusable asset archive.

For deeper design notes, read:

- `references/video-context-schema.md` for artifact schemas.
- `references/whisper-transcription.md` for standalone and batch transcription details.
- `references/whisper-merge-notes.md` for the `bggg-tiktok-whisper` comparison and merge decision.
- `references/tiktok-editing.md` for TikTok editing heuristics.
- `references/source-projects.md` for what was copied from Popcorn and related video-understanding projects.
