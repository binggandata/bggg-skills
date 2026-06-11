# Source Projects Reference

This note records the video-reading projects studied while designing this skill. The projects are not vendored in this open-source copy. The runtime scripts in this skill are copied/adapted into `scripts/` and do not import those projects.

## Studied Projects

| Project | Reference path | Commit read | What was copied as a pattern |
|---|---|---:|---|
| Popcorn | upstream repo | `e6a2b28` | FFprobe metadata, FFmpeg scene detection with `select=gt(scene,N)`, keyframe bundle, transcript-first agent workflow |
| video-understanding-engine | upstream repo | `89d9f43` | Multi-layer context: metadata, transcript, selected frames, frame analysis, summary/caption synthesis |
| video-understanding-local | upstream repo | `9f0fe77` | Fully-local privacy posture and combining Whisper speech with visual scene understanding |
| video-analyzer | upstream repo | `2b095fa` | JSON analysis output, frame-by-frame reasoning, Whisper segments with timestamps |

## Design Decisions

### Keep runtime self-contained

The reference projects use Node MCP, OpenCV, CLIP, local VLMs, Ollama, Hugging Face models, or packaged Python dependencies. This skill keeps the MVP runtime to:

- Required: `ffmpeg`, `ffprobe`
- Optional: `whisper-cli` or `whisper-cpp`
- Optional: `tesseract`

This makes the skill usable on a normal Codex/macOS setup without forcing a model stack install.

### Use artifacts, not APIs, as the contract

Popcorn returns analysis through MCP. This skill writes durable project artifacts:

- `metadata.json`
- `transcript.srt`
- `scenes.json`
- `keyframes/`
- `contact_sheet.jpg`
- `audio_events.json`
- `ocr.json`
- `timeline.md`
- `edit_plan.json`

Artifacts are easier for Codex to read, search, diff, archive, and reuse across editing tasks.

### Copy useful behavior, not project dependencies

Copied/adapted patterns:

- FFprobe JSON metadata extraction.
- FFmpeg audio extraction to 16kHz mono WAV.
- whisper.cpp CLI invocation.
- FFmpeg scene timestamp parsing from `showinfo`.
- Parallel-project folder convention with analysis and output assets.
- A manifest file as the single index of generated assets.

Not copied:

- MCP server implementation.
- Base64 inline frame transport.
- Heavy CLIP / VLM / Ollama model pipelines.
- Web UI layers.
- External package installation flows.

## When To Revisit References

Revisit the upstream projects only when improving this skill's internals:

- Need better scene detection presets: inspect Popcorn `src/presets.ts` and `src/ffmpeg.ts`.
- Need true vision captions: inspect `video-analyzer/video_analyzer/analyzer.py`.
- Need CLIP-based frame novelty: inspect `video-understanding-engine/frame_selection.py`.
- Need offline VLM summarization: inspect `video-understanding-local`.

For normal video analysis tasks, do not load these references; run this skill's scripts instead.
