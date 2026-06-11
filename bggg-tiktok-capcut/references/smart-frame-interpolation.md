# Smart Frame Interpolation

This capability is only for high-quality, performance-heavy frame interpolation before a video is imported into CapCut or before a draft is rebuilt. It is not a beat-sync tool and it is not a general AI-artifact repair method.

## Backend Policy

Use local RIFE ncnn Vulkan only:

```text
rife-ncnn-vulkan + rife-v4.6
spatial TTA on
temporal TTA on
target fps 60 by default
```

Do not silently fall back to FFmpeg `minterpolate`, frame blending, or simple optical-flow interpolation. Those methods can create liquid faces, warped hands, drifting logo text, and melting backgrounds. If RIFE is missing, stop and ask for the backend or set:

```bash
export BGGG_RIFE_NCNN="/path/to/rife-ncnn-vulkan"
export BGGG_RIFE_MODEL="/path/to/rife-v4.6"
```

The script also searches this skill's optional local backend folder:

```text
bggg-tiktok-capcut/tools/rife-ncnn-vulkan-20221029-macos/
```

## Command

Whole video to 60fps, preserving audio:

```bash
node scripts/smart-frame-interpolate.mjs \
  --input "/path/to/source.mp4" \
  --output "/path/to/source_60fps_rife.mp4"
```

Specific continuous range only:

```bash
node scripts/smart-frame-interpolate.mjs \
  --input "/path/to/source.mp4" \
  --output "/path/to/intro_60fps_rife.mp4" \
  --start 0 \
  --end 2.0
```

Use explicit safe segments:

```json
{
  "segments": [
    {"label": "lead_in", "start": 0.0, "end": 2.0},
    {"label": "demo_motion", "start": 5.2, "end": 8.6}
  ]
}
```

```bash
node scripts/smart-frame-interpolate.mjs \
  --input "/path/to/source.mp4" \
  --output "/path/to/source_rife_segments.mp4" \
  --segments "/path/to/segments.json" \
  --no-keep-audio
```

## Cut Protection

The default mode runs scene-cut detection and splits the source before sending frames to RIFE. Never interpolate across:

- hard cuts
- jump cuts
- outfit or product swaps
- beat-hit frames
- text/logo changes
- generated-object shape changes

Interpolate only continuous motion inside one shot. This is the main reason the output avoids the liquid look.

## When To Use

Use this for:

- low-fps source videos that look choppy in CapCut
- slow-motion segments that show repeated frames
- AI-generated videos where a small continuous movement should feel smoother
- pre-import normalization to 60fps before draft creation

Do not use this to hide major AI defects. If hands, products, text, or physics are already wrong, follow `ai-artifact-qa.md` and either repair with B-roll/overlay or regenerate.
