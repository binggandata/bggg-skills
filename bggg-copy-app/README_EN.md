# bggg-copy-app

A clean-room, high-fidelity **Android app replication** methodology skill: take over a real device via ADB → parse `uiautomator` trees + screenshots → specify pages/tokens/states → rebuild natively or cross-platform → compare the same flows step by step and verify behavior-level parity (duration, ownership, billing, notifications, failure recovery) → archive evidence and ship/open-source.

Distilled from the FlowClone project (a clean-room replication of Google Flow), verified at L3 depth on a real device.

## Install

### Codex

```bash
mkdir -p ~/.codex/skills
cp -R bggg-copy-app ~/.codex/skills/
```

Or symlink during development:

```bash
ln -s "$PWD/bggg-copy-app" ~/.codex/skills/bggg-copy-app
```

### DeepSeek Harness

```bash
mkdir -p ~/.agents/skills
cp -R bggg-copy-app ~/.agents/skills/
# project-level: <project>/.dsh/skills/bggg-copy-app/
```

## Usage

Ask the agent to “replicate this Android app with bggg-copy-app”, or load the `bggg-copy-app` skill. Entry: `SKILL.md`.

## Contents

- `SKILL.md` — workflow, hard rules, L0–L5 depth levels, resource index
- `references/` — device/exploration protocol, UI parsing, depth standards, behavior audit, native rebuild, 30 pitfalls, DSH workflow, delivery checklist, FlowClone case study
- `templates/` — project plan, exploration log, UI diff table, behavior audit, acceptance report
- `scripts/` — `adb-check.sh`, `ui.py` (uiautomator XML parser/tapper), `cap.sh`
- `evals/` — sample evaluation prompts

## License

MIT. REA / craft-anything are referenced as methodology comparisons only; no code from them is included.
