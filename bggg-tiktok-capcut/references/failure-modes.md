# CapCut Failure Modes

## Draft Folder Exists But CapCut Homepage Does Not Show It

Likely causes:

- `root_meta_info.json` is missing the draft or has stale fields.
- `draft_info.json.path` still points to the template draft.
- `Timelines/project.json.main_timeline_id` does not match `draft_info.id`.
- `Timelines/<draft_info.id>/` is missing.
- Nested `draft_info.json`, `template.tmp`, or `template-2.tmp` still contain old template IDs or names.
- CapCut was open and cached the old index.

Note: after CapCut loads a draft, it may rewrite some `path` fields to a value like `##_draftpath_placeholder_<UUID>_##`. Treat that as valid CapCut-owned state, not as a broken path.

Fix:

1. Run `scripts/validate-capcut-draft.mjs --draft "<draft-name>"`.
2. Regenerate with `scripts/create-capcut-draft.mjs --force ...`.
3. Quit CapCut completely and reopen it.

## Unsupported Media / No Access

Likely causes:

- Video material path points to a missing source file.
- A nested timeline copy still references the old source video.
- CapCut cache under `Timelines/<id>/attachment/patch` contains stale media refs.

Fix:

- Make the video path absolute and readable.
- Regenerate the draft with `--force`.
- Remove stale patch cache only inside the generated draft if validation still fails.

## Transition Appears At Video End

Cause: transition material ref was attached to the final segment instead of the previous segment.

Fix:

- Put the transition ref on the segment before the cut.
- Ensure the final segment has no transition ref.
- Re-run validation and inspect in CapCut.

## Subtitle Overflow

Symptom: subtitle text runs outside the 9:16 canvas.

Fix:

- Split long captions into shorter segments.
- Insert newline breaks.
- Use a template with a sane font size and line width.

## Abrupt Ending

Symptom: final caption or visual action ends mid-thought.

Fix:

- Trim the source video before draft generation, or regenerate with a cleaner source.
- Do not add a transition at the very end to hide an unfinished ending.

## Liquid Frame Interpolation Artifacts

Symptom: faces, hands, logos, text, or backgrounds look melted, warped, oily, or blended between shots.

Fix:

- Use `scripts/smart-frame-interpolate.mjs` with local RIFE.
- Do not use FFmpeg `minterpolate` fallback.
- Split at scene cuts and interpolate only continuous motion.
- Never interpolate across product swaps, text/logo changes, or hard cuts.
