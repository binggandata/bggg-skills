# bggg-tiktok-search

[中文](./README.md) | English

`bggg-tiktok-search` is a read-only TikTok research skill for Codex-style agents. It uses the user's real local Chrome session through WebBridge, Chrome/CDP, Apple Events, the Codex Chrome Extension, or Computer Use, then saves structured JSON/CSV/Markdown notes and screenshots for later analysis.

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
python3 -m pip install playwright
```

Verify:

```bash
python3 scripts/tk_research.py check-cdp
```

Search videos:

```bash
python3 scripts/tk_research.py search "portable blender" --limit 30
```

Collect creator videos:

```bash
python3 scripts/tk_research.py creator "https://www.tiktok.com/@creator" --limit 50
```

Outputs are written under `projects/tiktok-research/`.

## Safety

This skill is for reading, scrolling, screenshotting, and collecting visible research data. It should not like, follow, comment, DM, post, edit account settings, bypass CAPTCHA, or bypass safety pages. Do not commit cookies, browser profiles, screenshots, CSV/JSON research exports, or other run artifacts.
