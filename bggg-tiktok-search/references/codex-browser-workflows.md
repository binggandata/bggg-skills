# Codex Browser Workflows

`bggg-tiktok-search` has three browser-control paths. Pick the least fragile path that can complete the user's TikTok research task.

## Path Priority

1. `scripts/tk_research.py` through Chrome CDP 9222.
2. `chrome:Chrome` through the Codex Chrome Extension.
3. `computer-use:computer-use` against the visible macOS Google Chrome app.

Do not use headless browser automation for TikTok research. TikTok often serves different pages or blocks automation when the browser is not the user's real Chrome session.

## Chrome Extension Path

Use this path when the user mentions `@chrome`, CDP is unavailable, or the task depends on the user's existing Chrome tabs and login state.

Workflow:

1. Follow the `chrome:Chrome` skill setup and safety rules.
2. List open tabs and claim an existing TikTok tab when possible.
3. If no useful tab exists, open TikTok search, a creator profile, or the user-provided URL.
4. Use DOM snapshots first for links, handles, titles, and visible metrics.
5. Use screenshots when DOM text is ambiguous, missing, or visually encoded.
6. Save extracted items and evidence under `projects/tiktok-research/`.
7. Finalize Chrome tabs according to the Chrome skill; keep only user-facing handoff pages.

Recommended use cases:

- Search TikTok with an already authenticated profile.
- Inspect a creator's visible videos.
- Continue from a page the user already opened.
- Capture screenshots as evidence.

## Computer Use Path

Use this path when the Chrome extension is not available or when the TikTok UI must be operated visually.

Workflow:

1. Follow the `computer-use:computer-use` skill setup and safety rules.
2. Read the current app state before acting.
3. Operate Google Chrome by clicking, typing, scrolling, and reading visible content.
4. Capture screenshots for each meaningful page state or result batch.
5. Record only what is visible and defensible: URL, handle, display name, title/description, visible metrics, dates, screenshot path, and short notes.
6. Ask the user to handle login, CAPTCHA, safety interstitials, or blocked/age-gated states.

Good Computer Use targets:

- TikTok search pages that render poorly in DOM snapshots.
- Creator pages where metrics are only visually clear.
- Modal-heavy flows, cookie banners, region prompts, or language prompts.
- User-controlled current browser sessions.

## Safety Boundaries

Allowed without extra confirmation:

- Opening TikTok pages.
- Searching keywords.
- Scrolling and reading visible results.
- Taking screenshots.
- Downloading public pages or media when the user asked for research/download.

Do not perform without action-time confirmation:

- Like, follow, comment, share, repost, DM, publish, subscribe, or change account settings.
- Upload files.
- Submit forms that transmit sensitive user data.
- Accept browser permissions such as camera, microphone, or location.

Never solve CAPTCHAs or bypass browser/web safety barriers. Ask the user to take over and continue once the page is usable.

## Manual Output Contract

When CDP scripts are not used, create a manual run folder:

```text
bggg-tiktok-search/projects/tiktok-research/YYYYMMDD_HHMMSS_manual_<slug>/
├── collected_items.json
├── research_notes.md
└── screenshots/
```

`collected_items.json`:

```json
{
  "run_id": "manual-20260509-173000",
  "method": "chrome-plugin",
  "query": "portable blender",
  "source_url": "https://www.tiktok.com/search?q=portable%20blender",
  "captured_at": "2026-05-09T17:30:00+08:00",
  "items": [
    {
      "url": "https://www.tiktok.com/@creator/video/123",
      "author": "@creator",
      "author_url": "https://www.tiktok.com/@creator",
      "title": "Visible title or caption",
      "metric_1": "12.3K likes",
      "metric_2": "visible secondary metric",
      "date": "visible date",
      "raw_text": "Short visible evidence from the card",
      "screenshot": "screenshots/page_001.png",
      "notes": "Why this result matters"
    }
  ],
  "warnings": [
    "Metrics are visible-page estimates and should be manually spot checked."
  ]
}
```

`research_notes.md` should summarize:

- Task and query.
- Browser-control method used.
- Screenshot list.
- Top candidates.
- Content patterns and hooks.
- Follow-up recommendations for download, transcription, or deeper video reading.
