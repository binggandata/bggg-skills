# bggg-tiktok-whisper Merge Notes

`bggg-tiktok-whisper` overlapped with `bggg-tiktok-readvideo` on local whisper.cpp transcription, but it had a narrower and useful batch-ASR surface.

## What Already Existed In ReadVideo

- Full video project creation under `projects/YYYYMMDD_slug/`.
- `ffprobe` metadata.
- whisper.cpp transcription into `analysis/transcript.txt`, `analysis/transcript.srt`, and optional JSON.
- SRT parsing for timeline scene excerpts.
- Scene detection, keyframes, contact sheet, audio events, OCR, timeline, and edit plan template.

## What Whisper Added

- Transcript-only workflow for when no visual analysis is needed.
- Video and audio input support: `.mp4`, `.mov`, `.webm`, `.mkv`, `.m4v`, `.mp3`, `.m4a`, `.wav`, `.aac`, `.flac`.
- Folder and recursive batch transcription.
- Default output beside each source in `transcripts/`.
- Shared `--output-dir` support for batch jobs.
- Skip-existing behavior unless `--force` is set.
- `transcription_manifest.json` for batch status, transcript paths, model path, and errors.

## Merge Decision

Keep `scripts/analyze_video.py` as the full video-understanding pipeline, and add `scripts/transcribe_video.py` as the lightweight transcript-only entrypoint.

This avoids forcing every ASR request through scene detection/OCR/keyframe extraction while keeping the public skill surface consolidated under `bggg-tiktok-readvideo`.

The old source folder is archived at `references/merged-bggg-tiktok-whisper-source/` with its original `SKILL.md` renamed to `SKILL.source.md`, so it does not register as a separate skill when scanning top-level skill folders.
