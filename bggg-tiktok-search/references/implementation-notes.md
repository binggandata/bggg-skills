# Implementation Notes

## Architecture

This skill uses several real-Chrome control paths:

1. WebBridge to call a local browser bridge service when the user has one installed.
2. Playwright's `chromium.connect_over_cdp()` to attach to a local Chrome instance that the user started with remote debugging enabled.
3. macOS Apple Events through `scripts/tk_real_chrome.py`.
4. Codex's `chrome:Chrome` skill to control the user's Chrome through the Codex Chrome Extension.
5. Codex's `computer-use:computer-use` skill to operate the visible macOS Google Chrome UI when plugin/DOM automation is not enough.

That real-browser emphasis is the key difference from `kudosx/claude-skill-browser-use`, which mainly launches or reuses its own persistent browser profile.

Recommended Chrome startup command on macOS:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --profile-directory="Default" \
  --no-first-run \
  --disable-blink-features=AutomationControlled
```

Verify CDP:

```bash
python3 bggg-tiktok-search/scripts/tk_research.py check-cdp
```

## Why CDP

- It inherits the user's current TikTok cookies, localStorage, region, language, and account state.
- It avoids maintaining a separate `.auth/profiles/*` profile for each account.
- It lets the human user intervene in the same Chrome window when TikTok asks for login, CAPTCHA, consent, or manual confirmation.

Playwright's CDP connection is lower fidelity than Playwright's native browser protocol. Keep the automation simple: page navigation, locators, screenshots, scrolling, and `page.evaluate()` extraction. Avoid depending on complex browser-context features.

## Why Chrome Plugin / Computer Use

Use the Codex Chrome plugin when CDP is not running, when the user explicitly requests `@chrome`, or when a task should continue from an already open TikTok tab. It keeps work inside the user's authenticated Chrome profile and provides DOM snapshots, screenshots, and controlled clicks/typing through the Chrome Extension.

Use Computer Use when the Chrome Extension is unavailable, when TikTok's DOM is too unstable to trust, or when the task requires visual operation of the actual app window. This is especially useful for cookie banners, region prompts, modal-heavy pages, creator pages with visual metrics, or user-driven current-page workflows.

Neither fallback path should post, like, follow, comment, DM, upload, edit account settings, bypass CAPTCHA, or bypass browser safety pages. For search, reading, scrolling, screenshots, and visible-result sampling, they are appropriate research tools.

## Extractor Strategy

TikTok changes class names often, so the script extracts from stable URL patterns first:

- Video URLs: `a[href*="/video/"]`
- Creator URLs: `a[href*="/@"]`
- Author handle: parsed from `/@handle/video/...`
- Video ID: parsed from `/video/<id>`

Text fields are best-effort. Use `raw_text` as evidence when exact fields like likes, views, date, or caption cannot be cleanly separated from the DOM.

## Output Contract

Each run creates a timestamped folder under:

```text
bggg-tiktok-search/projects/tiktok-research/
```

Every research run writes:

- `*.json`: canonical structured output
- `*.csv`: spreadsheet-friendly table
- `*.md`: quick analyst note
- `screenshots/*.png`: evidence image when possible

Manual Chrome-plugin or Computer Use runs should use:

```text
bggg-tiktok-search/projects/tiktok-research/YYYYMMDD_HHMMSS_manual_<slug>/
```

Required manual files:

- `collected_items.json`: structured visible results with URLs, handles, titles, metrics, dates, screenshot paths, and notes.
- `research_notes.md`: analyst summary, top candidates, content patterns, and follow-up recommendations.
- `screenshots/`: evidence images captured during navigation and scrolling.

See `references/codex-browser-workflows.md` for the manual JSON schema and browser-control selection rules.

## Reference Project

The browser-use projects studied for this skill are not vendored in the open-source copy. Use this note for the absorbed patterns: prefer stable URL extraction over brittle CSS classes, keep browser automation simple, and keep all evidence files under ignored `projects/`.
