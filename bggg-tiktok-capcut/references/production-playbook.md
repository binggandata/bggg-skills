# CapCut Draft Playbook

Use this reference when building or debugging a CapCut draft from an AI-generated video.

## Directory Model

Default draft root:

```text
~/Movies/CapCut/User Data/Projects/com.lveditor.draft/
```

A valid generated draft should include:

```text
<draft-name>/
├── draft_info.json
├── draft_info.json.bak
├── draft_meta_info.json
├── draft_cover.jpg
├── template-2.tmp
├── draft_settings
├── Resources/
├── Timelines/
│   ├── project.json
│   ├── project.json.bak
│   └── <draft_info.id>/
│       ├── draft_info.json
│       ├── draft_info.json.bak
│       ├── template.tmp
│       └── template-2.tmp
└── ai_cut_manifest.json
```

CapCut does not only read the top-level `draft_info.json`. Keep the nested timeline copies and `Timelines/project.json` synchronized with `draft_info.id`.

## Template Selection

Choose a template draft that already has the style you want:

- subtitle font, color, background, border, shadow
- one useful transition at the cut point
- animation/material style if needed
- same target aspect ratio when possible

The template provides style and structure only. The generated draft must replace all source video paths with the new AI video path.

## Caption Flow

Use either explicit captions or SRT:

```bash
--captions "Hook\nStep 1\nStep 2"
--srt "/path/to/subtitles.srt"
```

The script writes CapCut text materials and text track segments while copying the first template text style.

## Transition Flow

CapCut stores transitions as material refs on a video segment. Attach the transition to the segment before the cut.

Correct:

```text
segment 1: extra_material_refs includes transition
segment 2: no transition ref
```

Wrong:

```text
segment 1: no transition ref
segment 2: extra_material_refs includes transition
```

The wrong structure can make CapCut show the transition at the end of the video.

## Validation

Run this after generation:

```bash
node scripts/validate-capcut-draft.mjs --draft "<draft-name>"
```

If a copied template name or old media path might remain, add:

```bash
--stale-marker "OLD_TEMPLATE_NAME"
--stale-marker "/old/source/video.mp4"
```

## CapCut Reload

If CapCut was open while writing the draft, quit CapCut completely and reopen it. The homepage list is driven by `root_meta_info.json` plus per-draft metadata and can cache stale state while the app is running.

## Final QA

For visual QA, sample frames from the final draft timeline:

```bash
node scripts/extract-ai-artifact-frames.mjs \
  --draft "<draft-name>" \
  --output-root ./ai-artifact-qa
```

Then review the contact sheet and create an `ai_artifact_review.json` only for publish-blocking AI issues.
