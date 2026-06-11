# TikTok Editing Playbook

Use this when the user gives broad creative instructions and the edit plan needs judgment.

## Default Deliverable

- 1080x1920, 30fps, H.264 MP4, AAC audio.
- Runtime: 15-45 seconds unless the user asks for a different length.
- Structure: Hook -> proof/demo -> value beat -> CTA or loop-back ending.
- First frame should already show the product, result, or visual payoff.

## AI-Generated Video Checks

Scan extracted frames before deciding cuts:

- Remove malformed hands, faces, logos, warped product text, flicker, abrupt style changes, and failed camera moves.
- Prefer segments with clear subject motion, product visibility, and clean negative space for subtitles.
- If the AI clip is beautiful but slow, speed it up 1.05-1.25x rather than adding unnecessary cuts.
- If the source has no useful audio, make captions/overlays carry the story and use BGM rhythm for pacing.

## Hook Patterns

- Result first: "This is not a render. It is the final ad."
- Pain point: "Your product video looks expensive until the first 3 seconds fail."
- Contrast: "Before: flat product shot. After: TikTok-ready UGC."
- Offer: "3 clips, 1 product, 30 seconds."
- Curiosity: "The AI made the shot. The edit made it sell."

## Cut Rhythm

- 0.0-3.0s: hook overlay and strongest shot.
- 3.0-10.0s: show the product/action clearly.
- 10.0-25.0s: benefits, proof, variations, or B-roll.
- Final 2.0s: CTA, price, discount, or loop back to the opening visual.

For visual-only AI clips, use 1.2-3.5 second shots. For voiceover, follow sentence boundaries and avoid cutting mid-word.

## Reframing

- `blur-bg`: default for horizontal AI video, product demos, and content where cropping would lose important detail.
- `cover`: use when the subject is centered and safe in a vertical crop.
- `contain`: use for full-body, full-product, before/after comparisons, or text-heavy source videos.
- `anchor`: use `left`, `right`, `top`, `bottom`, or combinations like `top-right` when the subject is not centered.

## Captions And Overlays

- Put spoken captions in the middle-lower safe zone, not at the bottom edge.
- Use short lines: Chinese 10-18 characters; English 3-7 words.
- Top overlay is for hook, price, offer, or product claim. Do not stack too much text.
- If the video will be posted on TikTok, avoid tiny disclaimer text in the bottom-right because the app UI covers it.

## Audio

- With voice: BGM volume 0.08-0.14.
- Without voice: BGM volume 0.18-0.28, or cut to beat.
- Add 30ms audio fades at cut boundaries to prevent pops.
- Avoid copyrighted BGM unless the user explicitly provides approved audio.

## Verification

Before delivery:

- `ffprobe` output is 1080x1920 or the requested target.
- Output has audio, even if it is silence or BGM only.
- Subtitles are readable on a phone-sized preview.
- Product and key text are not behind TikTok UI areas.
- First 1 second is not black, blank, or a slow fade-in.
