# AI Artifact QA Flow

Use this flow after draft generation/validation and before final delivery when the user asks to check AI video artifacts.

## Frame Sampling

Extract evenly spaced frames from the final draft timeline, not only from the raw source file.

Frame counts:

- About 15 seconds: 20 frames.
- About 30 seconds: 40 frames.

Use timestamped frame names so findings can map back to the video:

```bash
node scripts/extract-ai-artifact-frames.mjs --draft ai-video-capcut-001 --output-root /path/to/qa-run
node scripts/extract-ai-artifact-frames.mjs --video /path/to/ai-video.mp4 --output-root /path/to/qa-run
node scripts/extract-ai-artifact-frames.mjs --video-dir /path/to/videos --output-root /path/to/qa-run
```

The script writes:

```text
<output-root>/<draft-name>/
├── frames/
│   ├── 001_t00m00s000ms.jpg
│   └── ...
├── frames_manifest.json
└── ai_artifact_review.template.json
```

## Review Standard

Only mark obvious AI artifacts that affect publish quality. Do not mark ordinary aesthetic issues, mild awkwardness, subjective style dislikes, or normal Seedance variation.

Check each frame for:

1. Text, numbers, logos, package words, App UI: garbled, mirrored, skewed, missing strokes, impossible typography.
2. Hands, fingers, wrists, arms: extra/missing fingers, fused fingers, melted skin, reversed joints, impossible bends.
3. Hand-product intersection: hand passing through boxes, shoes, phones, parcels, bags.
4. Incomplete person/object: missing head, missing shoe half, cut-off product corner, missing body area.
5. Product deformation: wrong logo, color, structure, laces, zipper, screen, buttons, sole shape.
6. Object continuity: sudden appearance/disappearance, duplication, fusion, shape swapping.
7. Physics errors: floating objects, impossible unboxing, impossible grip.
8. Light, reflection, shadow, perspective errors that are obvious enough to hurt trust.
9. Background melting, bending, repetition, or deformation.
10. Over-smoothing, oily surface, local mushiness, edge warping.

## Review JSON Schema

Create `ai_artifact_review.json` from the template. Use this shape:

```json
{
  "draft_name": "ai-video-capcut-001",
  "duration_sec": 15.04,
  "issues": [
    {
      "frame_file": "frames/010_t00m07s100ms.jpg",
      "time_sec": 7.1,
      "severity": "high",
      "publish_blocking": true,
      "categories": ["hands", "hand_product_intersection"],
      "description": "Index finger visibly passes through the shoe upper while gripping it.",
      "recommended_fix": "Cover 4.1-10.1s with product B-roll or motion blur around the hand movement."
    }
  ]
}
```

Severity guidance:

- `critical`: obviously unpublishable at a glance.
- `high`: visible enough that a viewer may notice and lose trust.
- `medium`: visible only while pausing or looking carefully; fix only if there are few issues.
- `low`: do not process unless user asks for very strict QC.

## Fix Selection

A 15-second video normally has at most 1-2 publish-blocking AI issues. A 30-second video normally has at most 1-3. Select the most severe few; do not over-process the whole video.

Generate a repair plan:

```bash
node scripts/plan-ai-artifact-fixes.mjs \
  --review /path/to/ai_artifact_review.json \
  --output /path/to/ai_artifact_fix_plan.json
```

The plan expands each bad frame to a `time_sec ± 3s` window and recommends fixes. Merge overlapping windows.

## Fix Methods

Choose the least disruptive method that hides the artifact:

- **Transition**: use only at a semantic cut, product reveal, camera move, or change of demonstration state.
- **Sticker/overlay**: use when a localized text/logo/hand defect can be naturally covered.
- **Motion blur**: use for hand movement, fast object movement, or short unstable moments.
- **Depth blur**: use for background melting, bad text in the background, or mild perspective issues outside the subject.
- **Filter**: use for global over-smoothing/lighting mismatch when the issue is subtle.
- **B-roll**: use for severe hand/product deformation, impossible physics, product-logo defects, or central object failures.

Avoid:

- Adding a transition at the video end to hide a broken ending.
- Covering too many seconds when only one frame is bad.
- Marking non-publish-blocking aesthetic preferences as AI artifacts.

## Reporting

Report:

- Frame extraction output directory.
- Number of frames reviewed.
- Number of publish-blocking issues found.
- Fix windows and chosen fix type.
- Any drafts that should be regenerated instead of patched because the artifact is too central or persistent.
