# Edit Plan Schema

`scripts/render_tiktok_cut.py` renders a JSON edit plan. Paths are resolved relative to the project root, usually the parent of `plans/`.

## Top-Level Fields

```json
{
  "version": 1,
  "project": {},
  "settings": {},
  "clips": [],
  "captions": [],
  "overlays": [],
  "captions_file": "transcripts/source.srt",
  "bgm": {},
  "watermark": {},
  "export": {}
}
```

## project

```json
{
  "title": "Product hook",
  "platform": "tiktok",
  "target": {"width": 1080, "height": 1920, "fps": 30}
}
```

Use 1080x1920 for TikTok unless the user asks for another format.

## settings

```json
{
  "fit": "blur-bg",
  "anchor": "center",
  "grade": "punch",
  "caption_style": "tiktok-bold",
  "caption_font_size": 86,
  "hook_font_size": 92,
  "font": "Arial",
  "voice_volume": 1.0,
  "output_name": "final_tiktok.mp4"
}
```

- `fit`: `blur-bg`, `cover`, or `contain`.
- `anchor`: `center`, `left`, `right`, `top`, `bottom`, or combinations like `top-right`. Used by `cover`.
- `grade`: `none`, `neutral`, `punch`, `warm`, `soft`, or a raw FFmpeg filter string.
- `voice_volume`: volume multiplier for source audio.

## clips

```json
{
  "source": "raw/clip01.mp4",
  "start": 0.0,
  "end": 6.2,
  "speed": 1.0,
  "fit": "blur-bg",
  "anchor": "center",
  "grade": "punch",
  "volume": 1.0,
  "label": "HOOK",
  "caption": "Optional caption shown over this clip"
}
```

Each clip is trimmed from `start` to `end`, normalized to the target format, and concatenated in array order. The script applies short audio fades at boundaries.

## captions

```json
{
  "start": 0.0,
  "end": 2.4,
  "text": "第一眼就要看到结果",
  "style": "tiktok-bold",
  "max_chars": 18
}
```

Times are output-timeline seconds after all clips are concatenated. Styles:

- `tiktok-bold` or omitted: large white caption in the TikTok safe zone.
- `hook`, `top`, `headline`: yellow top hook.
- `badge`, `center`: centered badge.
- `minimal`, `clean`: smaller clean caption.

You can also set `captions_file` to an SRT file. It is treated as output-timeline SRT.

## overlays

Same structure as captions. Use overlays for hook, price, discount, CTA, product benefit, or claim text.

## bgm

```json
{
  "path": "assets/bgm/music.mp3",
  "volume": 0.12,
  "start": 0.0,
  "fade_in": 0.3,
  "fade_out": 0.8
}
```

Leave `path` empty for no BGM. The renderer loops BGM if it is shorter than the output.

## watermark

```json
{
  "path": "assets/images/logo.png",
  "width": 160,
  "position": "top-right",
  "margin": 48,
  "opacity": 0.85
}
```

Use only when the user wants branding. Avoid bottom-right on TikTok because the UI rail covers it.

## export

```json
{
  "crf": 20,
  "preset": "fast",
  "audio_bitrate": "192k",
  "faststart": true
}
```

Lower CRF means higher quality and larger file. Use CRF 18-22 for final exports.
