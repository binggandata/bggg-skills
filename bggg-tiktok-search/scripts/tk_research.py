#!/usr/bin/env python3
"""
TikTok research helper using Playwright over an existing Chrome CDP session.

Start Chrome first:
  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
    --remote-debugging-port=9222 \\
    --profile-directory="Default" \\
    --no-first-run \\
    --disable-blink-features=AutomationControlled
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import Page, sync_playwright
except ImportError:  # pragma: no cover
    Page = Any
    sync_playwright = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "projects" / "tiktok-research"
DEFAULT_CDP = "http://127.0.0.1:9222"


def slugify(value: str, fallback: str = "research") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_")
    return slug[:80] or fallback


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_playwright() -> None:
    if sync_playwright is None:
        raise SystemExit(
            "Missing dependency: playwright. Install with `python -m pip install playwright`."
        )


def check_cdp(cdp_endpoint: str = DEFAULT_CDP) -> dict[str, Any]:
    url = cdp_endpoint.rstrip("/") + "/json/version"
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def connect_page(cdp_endpoint: str = DEFAULT_CDP) -> tuple[Any, Any, Page]:
    ensure_playwright()
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(cdp_endpoint)
    except Exception:
        playwright.stop()
        raise

    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(15000)
    return playwright, browser, page


def wait_for_tiktok(page: Page) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass
    try:
        page.locator("button:has-text('Accept all')").first.click(timeout=1500)
    except Exception:
        pass
    try:
        page.wait_for_selector('a[href*="/video/"], a[href*="/@"]', timeout=12000)
    except Exception:
        pass


def scroll_collect(page: Page, limit: int, extractor: str, max_scrolls: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    stable_rounds = 0

    for _ in range(max_scrolls + 1):
        batch = page.evaluate(extractor)
        before = len(results)
        for item in batch:
            url = normalize_tiktok_url(item.get("url", ""))
            key = url or item.get("author_url") or item.get("author") or json.dumps(item, sort_keys=True)
            if not key or key in seen:
                continue
            seen.add(key)
            item["url"] = url
            results.append(item)
            if len(results) >= limit:
                return results[:limit]

        stable_rounds = stable_rounds + 1 if len(results) == before else 0
        if stable_rounds >= 3 and results:
            break
        page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 2, 1200))")
        page.wait_for_timeout(1300)

    return results[:limit]


def normalize_tiktok_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("/"):
        url = "https://www.tiktok.com" + url
    return url.split("?")[0]


VIDEO_EXTRACTOR = """
() => {
  const out = [];
  const links = Array.from(document.querySelectorAll('a[href*="/video/"]'));
  const seen = new Set();

  for (const link of links) {
    const href = link.getAttribute('href') || '';
    if (!href.includes('/video/')) continue;
    const url = href.startsWith('http') ? href : 'https://www.tiktok.com' + href;
    if (seen.has(url)) continue;
    seen.add(url);

    const card =
      link.closest('[data-e2e="search-video-card"]') ||
      link.closest('[data-e2e*="user-post-item"]') ||
      link.closest('div[class*="DivItemContainer"]') ||
      link.closest('div[class*="DivWrapper"]') ||
      link.closest('div') ||
      link;

    const raw = (card.innerText || card.textContent || '').replace(/\\s+/g, ' ').trim();
    const authorMatch = url.match(/\\/(@[^/]+)\\/video\\//);
    const videoMatch = url.match(/\\/video\\/(\\d+)/);
    const img = card.querySelector('img[alt], img[title]');
    const titleNode =
      card.querySelector('[data-e2e="video-desc"]') ||
      card.querySelector('[data-e2e="video-title"]') ||
      card.querySelector('span[class*="SpanText"]');
    const strong = Array.from(card.querySelectorAll('strong')).map(s => (s.textContent || '').trim()).filter(Boolean);
    const dateMatch = raw.match(/\\b(\\d+[smhdw] ago|\\d{1,2}-\\d{1,2}|\\d{4}-\\d{1,2}-\\d{1,2})\\b/i);

    out.push({
      url,
      video_id: videoMatch ? videoMatch[1] : '',
      author: authorMatch ? authorMatch[1] : '',
      author_url: authorMatch ? 'https://www.tiktok.com/' + authorMatch[1] : '',
      title: ((titleNode && titleNode.textContent) || (img && (img.alt || img.title)) || '').trim().slice(0, 300),
      metric_1: strong[0] || '',
      metric_2: strong[1] || '',
      date: dateMatch ? dateMatch[1] : '',
      raw_text: raw.slice(0, 800)
    });
  }
  return out;
}
"""


CREATOR_EXTRACTOR = VIDEO_EXTRACTOR


AUTHOR_EXTRACTOR = """
() => {
  const out = [];
  const links = Array.from(document.querySelectorAll('a[href*="/@"]'));
  const seen = new Set();

  for (const link of links) {
    const href = link.getAttribute('href') || '';
    const match = href.match(/\\/(@[^/?#]+)/);
    if (!match || href.includes('/video/')) continue;
    const author = match[1];
    const url = href.startsWith('http') ? href.split('?')[0] : 'https://www.tiktok.com/' + author;
    if (seen.has(url)) continue;
    seen.add(url);

    const card =
      link.closest('[data-e2e*="user-card"]') ||
      link.closest('[data-e2e*="search-user"]') ||
      link.closest('div[class*="DivUser"]') ||
      link.closest('div') ||
      link;
    const raw = (card.innerText || card.textContent || '').replace(/\\s+/g, ' ').trim();
    const img = card.querySelector('img[alt]');
    out.push({
      url,
      author,
      display_name: (img && img.alt) ? img.alt.trim() : '',
      raw_text: raw.slice(0, 800)
    });
  }
  return out;
}
"""


PROFILE_EXTRACTOR = """
() => {
  const text = (node) => node ? (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim() : '';
  const first = (selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const value = text(node);
      if (value) return value;
    }
    return '';
  };
  const href = (selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      if (node && node.href) return node.href;
    }
    return '';
  };
  const pathHandle = (location.pathname.match(/\\/(@[^/?#]+)/) || [])[1] || '';
  const raw = (document.body.innerText || document.body.textContent || '').replace(/\\s+/g, ' ').trim();
  const avatar = document.querySelector('img[alt][src]') || document.querySelector('img[src]');

  return {
    url: location.href.split('?')[0],
    handle: first(['[data-e2e="user-title"]', 'h1']) || pathHandle,
    display_name: first(['[data-e2e="user-subtitle"]', 'h2']) || '',
    bio: first(['[data-e2e="user-bio"]', '[data-e2e*="bio"]']) || '',
    followers_text: first(['strong[data-e2e="followers-count"]', '[data-e2e="followers-count"]']) || '',
    following_text: first(['strong[data-e2e="following-count"]', '[data-e2e="following-count"]']) || '',
    likes_text: first(['strong[data-e2e="likes-count"]', '[data-e2e="likes-count"]']) || '',
    website: href(['a[data-e2e="user-link"]', 'a[href^="http"]:not([href*="tiktok.com"])']) || '',
    avatar_url: avatar ? avatar.src : '',
    verified: !!document.querySelector('[data-e2e*="verified"], svg[aria-label*="Verified"], svg[aria-label*="verified"]'),
    raw_text: raw.slice(0, 1800)
  };
}
"""


def parse_count(value: str) -> int | None:
    if not value:
        return None
    text = value.strip().replace(",", "").replace(" ", "")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)([KkMmBb万萬亿億千]?)", text)
    if not match:
        return None
    number = float(match.group(1))
    suffix = match.group(2)
    multiplier = {
        "": 1,
        "K": 1_000,
        "k": 1_000,
        "M": 1_000_000,
        "m": 1_000_000,
        "B": 1_000_000_000,
        "b": 1_000_000_000,
        "千": 1_000,
        "万": 10_000,
        "萬": 10_000,
        "亿": 100_000_000,
        "億": 100_000_000,
    }[suffix]
    return int(number * multiplier)


def find_count_near_label(raw_text: str, label: str) -> str:
    if not raw_text:
        return ""
    patterns = [
        rf"([0-9][0-9,]*(?:\.[0-9]+)?\s*[KkMmBb万萬亿億千]?)\s*{label}",
        rf"{label}\s*([0-9][0-9,]*(?:\.[0-9]+)?\s*[KkMmBb万萬亿億千]?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text, re.I)
        if match:
            return match.group(1).strip()
    return ""


def enrich_profile_counts(profile: dict[str, Any]) -> None:
    raw = profile.get("raw_text", "")
    if not profile.get("followers_text"):
        profile["followers_text"] = find_count_near_label(raw, "Followers|粉丝|粉絲|フォロワー")
    if not profile.get("following_text"):
        profile["following_text"] = find_count_near_label(raw, "Following|正在关注|关注")
    if not profile.get("likes_text"):
        profile["likes_text"] = find_count_near_label(raw, "Likes|获赞|喜歡|いいね")
    profile["followers_count"] = parse_count(profile.get("followers_text", ""))
    profile["following_count"] = parse_count(profile.get("following_text", ""))
    profile["likes_count"] = parse_count(profile.get("likes_text", ""))


def extract_profile(page: Page) -> dict[str, Any]:
    profile = page.evaluate(PROFILE_EXTRACTOR)
    if profile.get("handle") and not profile["handle"].startswith("@"):
        profile["handle"] = "@" + profile["handle"].lstrip("@")
    if not profile.get("url") and profile.get("handle"):
        profile["url"] = "https://www.tiktok.com/" + profile["handle"]
    enrich_profile_counts(profile)
    return profile


def make_run_dir(output_dir: Path, label: str) -> Path:
    run_dir = output_dir / f"{now_stamp()}_{slugify(label)}"
    (run_dir / "screenshots").mkdir(parents=True, exist_ok=True)
    return run_dir


def write_outputs(run_dir: Path, stem: str, payload: dict[str, Any]) -> dict[str, str]:
    json_path = run_dir / f"{stem}.json"
    csv_path = run_dir / f"{stem}.csv"
    md_path = run_dir / f"{stem}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = payload.get("items", [])
    write_csv(csv_path, rows)
    write_markdown(md_path, payload)
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "platform_keyword",
        "url",
        "creator_url",
        "video_id",
        "handle",
        "author",
        "author_url",
        "title",
        "display_name",
        "bio",
        "followers_text",
        "followers_count",
        "following_text",
        "following_count",
        "likes_text",
        "likes_count",
        "website",
        "verified",
        "source_video_url",
        "source_video_title",
        "source_video_date",
        "source_video_metric_1",
        "source_video_metric_2",
        "metric_1",
        "metric_2",
        "date",
        "raw_text",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# TikTok Research: {payload.get('label', '')}",
        "",
        f"- URL: {payload.get('page_url', '')}",
        f"- Collected: {payload.get('collected_at', '')}",
        f"- Count: {len(payload.get('items', []))}",
        "",
    ]
    screenshot = payload.get("screenshot")
    if screenshot:
        lines.extend([f"- Screenshot: `{screenshot}`", ""])
    for index, item in enumerate(payload.get("items", []), 1):
        title = item.get("title") or item.get("display_name") or item.get("raw_text", "")[:80]
        lines.extend(
            [
                f"## {index}. {title}",
                "",
                f"- URL: {item.get('url', '')}",
                f"- Author: {item.get('author', '')}",
                f"- Metrics: {item.get('metric_1', '')} {item.get('metric_2', '')}".strip(),
                f"- Date: {item.get('date', '')}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def screenshot(page: Page, run_dir: Path, label: str, full_page: bool = True) -> str:
    path = run_dir / "screenshots" / f"{slugify(label)}.png"
    page.screenshot(path=str(path), full_page=full_page)
    return str(path)


def command_check(args: argparse.Namespace) -> int:
    try:
        info = check_cdp(args.cdp)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "cdp": args.cdp, "browser": info}, ensure_ascii=False, indent=2))
    return 0


def command_search(args: argparse.Namespace) -> int:
    run_dir = make_run_dir(Path(args.output_dir), "search_" + args.keyword)
    encoded = urllib.parse.quote(args.keyword.lstrip("#"))
    url = f"https://www.tiktok.com/search/video?q={encoded}"
    playwright, browser, page = connect_page(args.cdp)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        wait_for_tiktok(page)
        items = scroll_collect(page, args.limit, VIDEO_EXTRACTOR, args.max_scrolls)
        shot = screenshot(page, run_dir, "search_evidence") if args.screenshot else ""
        payload = base_payload("search", args.keyword, page.url, items, shot)
        outputs = write_outputs(run_dir, "search_results", payload)
        print(json.dumps({"ok": True, "count": len(items), "run_dir": str(run_dir), "outputs": outputs}, ensure_ascii=False, indent=2))
        return 0
    finally:
        playwright.stop()


def command_authors(args: argparse.Namespace) -> int:
    run_dir = make_run_dir(Path(args.output_dir), "authors_" + args.keyword)
    encoded = urllib.parse.quote(args.keyword)
    url = f"https://www.tiktok.com/search/user?q={encoded}"
    playwright, browser, page = connect_page(args.cdp)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        wait_for_tiktok(page)
        items = scroll_collect(page, args.limit, AUTHOR_EXTRACTOR, args.max_scrolls)
        shot = screenshot(page, run_dir, "author_search_evidence") if args.screenshot else ""
        payload = base_payload("author-search", args.keyword, page.url, items, shot)
        outputs = write_outputs(run_dir, "author_results", payload)
        print(json.dumps({"ok": True, "count": len(items), "run_dir": str(run_dir), "outputs": outputs}, ensure_ascii=False, indent=2))
        return 0
    finally:
        playwright.stop()


def command_creator(args: argparse.Namespace) -> int:
    run_dir = make_run_dir(Path(args.output_dir), "creator_" + args.url.rstrip("/").split("/")[-1])
    playwright, browser, page = connect_page(args.cdp)
    try:
        page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        wait_for_tiktok(page)
        items = scroll_collect(page, args.limit, CREATOR_EXTRACTOR, args.max_scrolls)
        shot = screenshot(page, run_dir, "creator_homepage_evidence") if args.screenshot else ""
        payload = base_payload("creator", args.url, page.url, items, shot)
        outputs = write_outputs(run_dir, "creator_videos", payload)
        print(json.dumps({"ok": True, "count": len(items), "run_dir": str(run_dir), "outputs": outputs}, ensure_ascii=False, indent=2))
        return 0
    finally:
        playwright.stop()


def command_current(args: argparse.Namespace) -> int:
    run_dir = make_run_dir(Path(args.output_dir), "current_page")
    playwright, browser, page = connect_page(args.cdp)
    try:
        wait_for_tiktok(page)
        extractor = AUTHOR_EXTRACTOR if args.kind == "authors" else VIDEO_EXTRACTOR
        items = scroll_collect(page, args.limit, extractor, args.max_scrolls)
        shot = screenshot(page, run_dir, "current_page_evidence") if args.screenshot else ""
        payload = base_payload("current-" + args.kind, page.url, page.url, items, shot)
        outputs = write_outputs(run_dir, "current_page_results", payload)
        print(json.dumps({"ok": True, "count": len(items), "run_dir": str(run_dir), "outputs": outputs}, ensure_ascii=False, indent=2))
        return 0
    finally:
        playwright.stop()


def command_screenshot(args: argparse.Namespace) -> int:
    run_dir = make_run_dir(Path(args.output_dir), "screenshot_" + args.label)
    playwright, browser, page = connect_page(args.cdp)
    try:
        path = screenshot(page, run_dir, args.label, full_page=not args.viewport_only)
        print(json.dumps({"ok": True, "screenshot": path, "url": page.url}, ensure_ascii=False, indent=2))
        return 0
    finally:
        playwright.stop()


def command_influencers(args: argparse.Namespace) -> int:
    label = "influencers_" + "_".join(args.keywords)
    run_dir = make_run_dir(Path(args.output_dir), label)
    playwright, browser, page = connect_page(args.cdp)
    all_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}

    try:
        for keyword in args.keywords:
            encoded = urllib.parse.quote(keyword.lstrip("#"))
            search_url = f"https://www.tiktok.com/search/video?q={encoded}"
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            wait_for_tiktok(page)
            if args.screenshot:
                screenshot(page, run_dir, f"search_{keyword}", full_page=False)

            candidates = scroll_collect(page, args.candidate_limit, VIDEO_EXTRACTOR, args.search_scrolls)
            seen_handles: set[str] = set()
            qualified: list[dict[str, Any]] = []
            checked = 0

            for candidate in candidates:
                handle = (candidate.get("author") or "").strip()
                author_url = candidate.get("author_url") or (f"https://www.tiktok.com/{handle}" if handle else "")
                if not handle or handle in seen_handles:
                    continue
                seen_handles.add(handle)
                checked += 1

                try:
                    page.goto(author_url, wait_until="domcontentloaded", timeout=60000)
                    wait_for_tiktok(page)
                    page.wait_for_timeout(args.profile_delay_ms)
                    profile = extract_profile(page)
                except Exception as exc:
                    if args.verbose:
                        print(f"[warn] profile failed {author_url}: {exc}", file=sys.stderr)
                    continue

                followers = profile.get("followers_count")
                row = {
                    "platform_keyword": keyword,
                    "creator_url": profile.get("url") or author_url,
                    "url": profile.get("url") or author_url,
                    "handle": profile.get("handle") or handle,
                    "display_name": profile.get("display_name", ""),
                    "bio": profile.get("bio", ""),
                    "followers_text": profile.get("followers_text", ""),
                    "followers_count": followers,
                    "following_text": profile.get("following_text", ""),
                    "following_count": profile.get("following_count"),
                    "likes_text": profile.get("likes_text", ""),
                    "likes_count": profile.get("likes_count"),
                    "website": profile.get("website", ""),
                    "verified": profile.get("verified", False),
                    "source_video_url": candidate.get("url", ""),
                    "source_video_title": candidate.get("title", ""),
                    "source_video_date": candidate.get("date", ""),
                    "source_video_metric_1": candidate.get("metric_1", ""),
                    "source_video_metric_2": candidate.get("metric_2", ""),
                    "raw_text": profile.get("raw_text", ""),
                }

                if followers is not None and followers >= args.min_followers:
                    qualified.append(row)
                    all_rows.append(row)
                    if args.screenshot_profiles:
                        screenshot(page, run_dir, f"{keyword}_{row['handle']}", full_page=False)
                    print(
                        json.dumps(
                            {
                                "keyword": keyword,
                                "qualified": len(qualified),
                                "handle": row["handle"],
                                "followers": followers,
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    if len(qualified) >= args.per_keyword:
                        break
                elif args.keep_rejected:
                    row["rejected_reason"] = f"followers<{args.min_followers}"
                    all_rows.append(row)

                time.sleep(args.delay)

            summary[keyword] = {
                "candidate_count": len(candidates),
                "profiles_checked": checked,
                "qualified_count": len(qualified),
            }

        payload = base_payload("influencers", ", ".join(args.keywords), page.url, all_rows, "")
        payload["summary"] = summary
        payload["min_followers"] = args.min_followers
        payload["per_keyword_target"] = args.per_keyword
        outputs = write_outputs(run_dir, "influencers", payload)
        print(
            json.dumps(
                {"ok": True, "count": len(all_rows), "summary": summary, "run_dir": str(run_dir), "outputs": outputs},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        playwright.stop()


def base_payload(kind: str, label: str, page_url: str, items: list[dict[str, Any]], shot: str = "") -> dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
        "page_url": page_url,
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "screenshot": shot,
        "items": items,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TikTok research via Playwright connect_over_cdp.")
    parser.add_argument("--cdp", default=DEFAULT_CDP, help="Chrome CDP endpoint, default http://127.0.0.1:9222")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT), help="Directory for research runs.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-cdp", help="Verify that Chrome remote debugging is reachable.").set_defaults(func=command_check)

    search = sub.add_parser("search", help="Search TikTok videos by keyword.")
    search.add_argument("keyword")
    add_collect_args(search)
    search.set_defaults(func=command_search)

    authors = sub.add_parser("authors", help="Search TikTok creators by keyword.")
    authors.add_argument("keyword")
    add_collect_args(authors)
    authors.set_defaults(func=command_authors)

    creator = sub.add_parser("creator", help="Collect recent visible videos from a creator profile.")
    creator.add_argument("url")
    add_collect_args(creator)
    creator.set_defaults(func=command_creator)

    current = sub.add_parser("current", help="Extract videos or authors from the current browser page.")
    current.add_argument("--kind", choices=["videos", "authors"], default="videos")
    add_collect_args(current)
    current.set_defaults(func=command_current)

    shot = sub.add_parser("screenshot", help="Capture evidence from the current browser page.")
    shot.add_argument("label")
    shot.add_argument("--viewport-only", action="store_true")
    shot.set_defaults(func=command_screenshot)

    influencers = sub.add_parser("influencers", help="Find creators above a follower threshold for one or more keywords.")
    influencers.add_argument("keywords", nargs="+")
    influencers.add_argument("--per-keyword", type=int, default=10)
    influencers.add_argument("--min-followers", type=int, default=100_000)
    influencers.add_argument("--candidate-limit", type=int, default=120)
    influencers.add_argument("--search-scrolls", type=int, default=35)
    influencers.add_argument("--profile-delay-ms", type=int, default=1800)
    influencers.add_argument("--delay", type=float, default=0.8)
    influencers.add_argument("--screenshot", action="store_true", default=True)
    influencers.add_argument("--screenshot-profiles", action="store_true")
    influencers.add_argument("--keep-rejected", action="store_true")
    influencers.add_argument("--verbose", action="store_true")
    influencers.set_defaults(func=command_influencers)
    return parser


def add_collect_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--max-scrolls", type=int, default=18)
    parser.add_argument("--screenshot", action="store_true", default=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
