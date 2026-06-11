# Whisper Transcription

This note records the standalone transcription capability merged from `bggg-tiktok-whisper`.

## Local Dependencies

- `ffmpeg`: extracts a 16 kHz mono PCM WAV track from each source.
- `whisper-cli` or `whisper-cpp`: runs local whisper.cpp inference.
- ggml model files: the scripts search common user-level NGSpilot and whisper.cpp model folders.

Common model folders:

- `~/Library/Application Support/com.ngspilot.desktop/runtime-data/tiktok-asr/models`
- `~/Library/Application Support/NGSpilot/runtime/tiktok-asr/models`
- `~/.cache/whisper.cpp`
- `bggg-tiktok-readvideo/models/whisper`

## Standalone Flow

Use this when the user only needs ASR/transcripts and does not need video scenes, keyframes, OCR, or an edit plan:

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/video-or-audio"
```

Folder batch mode:

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/downloads" --recursive
```

The script accepts `.mp4`, `.mov`, `.webm`, `.mkv`, `.m4v`, `.mp3`, `.m4a`, `.wav`, `.aac`, and `.flac`.

## Outputs

Default output goes to a `transcripts/` folder beside each source. A shared `--output-dir` may be used for batch jobs.

Each run writes:

- `*.txt`: cleaned original-language transcript.
- `*.srt`: optional subtitles when `--srt` is set.
- `*.json`: optional whisper.cpp JSON when `--json` is set.
- `transcription_manifest.json`: source paths, transcript paths, statuses, model path, and errors.

Existing `.txt` transcripts are skipped by default. Use `--force` to regenerate.

## Relationship To Full Video Analysis

`scripts/analyze_video.py` still owns full video understanding: metadata, scenes, keyframes, contact sheet, audio events, OCR, timeline, and edit plan scaffolding.

`scripts/transcribe_video.py` is the lightweight path for transcript-only requests and batch ASR after downloading TikTok videos.
