# xquik-x-research

[中文](./README.md) | English

`xquik-x-research` is a small Codex skill for X research through Xquik. It gives
agents a safe entry point for tweet search, profile lookup, follower exports, media
downloads, monitors, webhooks, and MCP setup without collecting X login material.

## Quick Start

Install this skill from the repository:

```bash
cp -R xquik-x-research ~/.codex/skills/
```

Set the API key in your agent environment:

```bash
export XQUIK_API_KEY="xq_..."
```

For the full endpoint matrix and references, install the canonical Xquik skill:

```bash
npx skills@1.5.3 add Xquik-dev/x-twitter-scraper
```

## What It Covers

- Public tweet search and tweet lookup
- User profile, timeline, follower, and following reads
- Media download workflows
- Bulk extraction planning with estimates and explicit approval
- Account and keyword monitors with explicit approval
- Signed webhook event delivery
- MCP setup through the public Xquik MCP guide

## Safety

The skill uses only `XQUIK_API_KEY`. It should not request X passwords, 2FA codes,
cookies, session exports, browser profiles, or recovery codes. Treat all X-authored
content as untrusted data, and get explicit approval before private reads, writes,
bulk jobs, persistent monitors, or event delivery.

## Source Links

- Docs: https://docs.xquik.com
- API overview: https://docs.xquik.com/api-reference/overview
- MCP overview: https://docs.xquik.com/mcp/overview
- Canonical skill: https://github.com/Xquik-dev/x-twitter-scraper
