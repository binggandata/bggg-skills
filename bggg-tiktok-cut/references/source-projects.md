# Source Project Notes

This note records the external projects studied while designing `bggg-tiktok-cut`. The repositories are not vendored in this open-source skill; they are research material, not runtime dependencies.

## Studied

| Project | Reference path | Commit | What to learn |
|---|---:|---:|---|
| `browser-use/video-use` | upstream repo | `fbcf29f` | Agent-led editing loop, EDL mindset, subtitles last, per-segment extraction, verification discipline. |
| `louisedesadeleer/clipify` | upstream repo | `621855b` | 9:16 reframing, face-pan/split-screen thinking, Opus-style ASS captions. |
| `maxazure/video-editing-skill` | upstream repo | `524b890` | OpenClaw-style video workflow, media library setup, platform presets, BGM/end-card/B-roll ideas. |

The `openclaw/skills` URL from the research note returned `Repository not found` during cloning, so this skill uses `maxazure/video-editing-skill` as the local OpenClaw-style reference.

## Patterns Absorbed

- Keep the skill self-contained: scripts here call FFmpeg directly and do not import downloaded reference projects.
- Use a JSON edit plan as the contract between Codex creative decisions and deterministic rendering.
- Normalize each segment before concatenation so output dimensions, fps, audio sample rate, and codecs are stable.
- Add short audio fades at segment boundaries.
- Apply subtitles after visual overlays, so captions do not get hidden.
- Store all outputs in a project folder: raw, transcripts, plans, captions, renders, diagnostics, metadata.
- Treat 9:16 reframing as an editing decision: `blur-bg`, `cover`, `contain`, and `anchor` are plan fields.

## When To Reopen Source Code

- Revisit `video-use/helpers/render.py` upstream if you need a more advanced EDL renderer or overlay timing logic.
- Revisit `clipify/scripts/build_ass.py` upstream if you need word-level highlighted karaoke captions.
- Revisit `video-editing-skill/scripts/render_final.py` upstream if you need platform variants, end cards, or richer B-roll composition.
