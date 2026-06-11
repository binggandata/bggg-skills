# bggg-tiktok-search

TikTok research skill for Codex/Claude-style agents. It controls a real local Chrome browser through Playwright + CDP, Apple Events, WebBridge, the Codex Chrome Extension, or Computer Use, so it can reuse the user's existing TikTok login state for read-only research.

## Quick Start

Start Chrome with CDP:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --profile-directory="Default" \
  --no-first-run \
  --disable-blink-features=AutomationControlled
```

Install dependency if needed:

```bash
python -m pip install playwright
```

Verify:

```bash
python scripts/tk_research.py check-cdp
```

Search videos:

```bash
python scripts/tk_research.py search "portable blender" --limit 30
```

Collect creator videos:

```bash
python scripts/tk_research.py creator "https://www.tiktok.com/@creator" --limit 50
```

Outputs are written under `projects/tiktok-research/`.

## Codex Browser Paths

Preferred path:

```bash
python3 scripts/tk_research.py check-cdp
python3 scripts/tk_research.py search "portable blender" --limit 30
```

If CDP is unavailable but Codex can access the user's Chrome profile, use the `chrome:Chrome` skill to claim an existing TikTok tab or open a new one, then collect DOM snapshots and screenshots.

If the Chrome extension cannot connect, or TikTok needs visible manual operation, use `computer-use:computer-use` to operate the local Google Chrome app. Save manual runs under:

```text
projects/tiktok-research/YYYYMMDD_HHMMSS_manual_<slug>/
```

For details, see `references/codex-browser-workflows.md`.

Do not commit cookies, browser profiles, screenshots, CSV/JSON research exports, or other run artifacts.
