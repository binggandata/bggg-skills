#!/usr/bin/env python3
"""
TikTok research through the user's real Google Chrome via Apple Events.

Use this when Chrome's real Default profile is required and CDP is unavailable
for the default user data directory. Chrome must have:
View > Developer > Allow JavaScript from Apple Events enabled.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "projects" / "tiktok-research"
TARGET_WINDOW_ID: str | None = None
TARGET_TAB_ID: str | None = None


def slugify(value: str, fallback: str = "research") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_")
    return slug[:90] or fallback


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def osa(script: str, timeout: int = 60) -> str:
    return subprocess.check_output(["osascript", "-e", script], text=True, timeout=timeout).strip()


def start_research_tab() -> tuple[str, str]:
    out = osa(
        """
        tell application "Google Chrome"
          set w to make new window
          set URL of active tab of w to "about:blank"
          return (id of w as text) & ":" & (id of active tab of w as text)
        end tell
        """
    )
    window_id, tab_id = out.split(":", 1)
    return window_id.strip(), tab_id.strip()


def target_prefix() -> str:
    if not TARGET_WINDOW_ID or not TARGET_TAB_ID:
        raise RuntimeError("Chrome research tab has not been initialized.")
    return (
        'tell application "Google Chrome"\n'
        f"  set targetWindow to first window whose id is {TARGET_WINDOW_ID}\n"
        f"  set targetTab to first tab of targetWindow whose id is {TARGET_TAB_ID}\n"
    )


def chrome_js(js: str, timeout: int = 60) -> Any:
    wrapped = "JSON.stringify((() => { " + js + " })())"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(wrapped)
        js_path = fh.name
    script = (
        f'set jsCode to read POSIX file {json.dumps(js_path)} as «class utf8»\n'
        + target_prefix()
        + "  execute targetTab javascript jsCode\n"
        + "end tell"
    )
    try:
        out = osa(script, timeout=timeout)
    finally:
        Path(js_path).unlink(missing_ok=True)
    if not out:
        return None
    return json.loads(out)


def chrome_set_url(url: str) -> None:
    script = target_prefix() + f"  set URL of targetTab to {json.dumps(url)}\nend tell"
    osa(script)


def chrome_active_url() -> str:
    return osa(target_prefix() + "  return URL of targetTab\nend tell")


def wait_page(min_video_links: int = 1, timeout: int = 25) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            last = chrome_js(
                """
                return {
                  url: location.href,
                  title: document.title,
                  ready: document.readyState,
                  text: (document.body.innerText || '').slice(0, 800),
                  videoLinks: document.querySelectorAll('a[href*="/video/"]').length,
                  authorLinks: document.querySelectorAll('a[href*="/@"]').length
                };
                """,
                timeout=10,
            )
            if last.get("ready") == "complete" and last.get("videoLinks", 0) >= min_video_links:
                return last
        except Exception:
            pass
        time.sleep(1)
    return last


def wait_profile(handle: str, timeout: int = 20) -> dict[str, Any]:
    expected = handle.lstrip("@").lower()
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            last = chrome_js(
                """
                const raw = (document.body.innerText || '').replace(/\\s+/g, ' ').trim();
                return {
                  url: location.href,
                  pathname: location.pathname,
                  title: document.title,
                  ready: document.readyState,
                  hasFollowers: /粉丝|粉絲|Followers/i.test(raw),
                  text: raw.slice(0, 600)
                };
                """,
                timeout=10,
            )
            path = (last.get("pathname") or "").lower()
            if expected in path and last.get("ready") == "complete" and last.get("hasFollowers"):
                return last
        except Exception:
            pass
        time.sleep(0.8)
    return last


def parse_count(value: str | None) -> int | None:
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


def extract_candidates() -> list[dict[str, Any]]:
    return chrome_js(
        r"""
        const out = [];
        const seen = new Set();
        const normalize = (href) => href.startsWith('http') ? href.split('?')[0] : 'https://www.tiktok.com' + href.split('?')[0];
        const bestCard = (link) => {
          let node = link;
          let best = link;
          for (let i = 0; i < 9 && node; i++, node = node.parentElement) {
            const text = (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim();
            if (text.length > 35 && text.length < 1400) best = node;
          }
          return best;
        };

        for (const link of Array.from(document.querySelectorAll('a[href*="/video/"]'))) {
          const href = link.getAttribute('href') || '';
          const match = href.match(/\/(@[^/]+)\/video\/(\d+)/);
          if (!match) continue;
          const handle = match[1];
          const videoId = match[2];
          if (seen.has(handle)) continue;
          seen.add(handle);
          const card = bestCard(link);
          const raw = (card.innerText || card.textContent || '').replace(/\s+/g, ' ').trim();
          const lines = raw.split(/\n+/).map(x => x.trim()).filter(Boolean);
          const title = lines.find(x => x.length > 20 && !/^(\d|[0-9.]+[KMB万])/.test(x)) || '';
          const dateMatch = raw.match(/\b(\d+[smhdw]\s*ago|\d{1,2}-\d{1,2}|\d{4}-\d{1,2}-\d{1,2}|[0-9]+\s*天前)\b/i);
          const strong = Array.from(card.querySelectorAll('strong')).map(x => (x.textContent || '').trim()).filter(Boolean);
          out.push({
            handle,
            author_url: 'https://www.tiktok.com/' + handle,
            source_video_url: normalize(href),
            source_video_id: videoId,
            source_video_title: title,
            source_video_date: dateMatch ? dateMatch[1] : '',
            source_video_metric_1: strong[0] || '',
            source_video_metric_2: strong[1] || '',
            source_raw_text: raw.slice(0, 900)
          });
        }
        return out;
        """,
        timeout=30,
    ) or []


def scroll_search(keyword: str, candidate_limit: int, max_scrolls: int, delay: float) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(keyword)
    chrome_set_url(f"https://www.tiktok.com/search/video?q={encoded}&t={int(time.time() * 1000)}")
    wait_page(min_video_links=1, timeout=35)

    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    stable_rounds = 0
    for _ in range(max_scrolls + 1):
        before = len(candidates)
        for item in extract_candidates():
            handle = item.get("handle")
            if not handle or handle in seen:
                continue
            seen.add(handle)
            item["source_query"] = keyword
            candidates.append(item)
            if len(candidates) >= candidate_limit:
                return candidates
        stable_rounds = stable_rounds + 1 if len(candidates) == before else 0
        if stable_rounds >= 5 and candidates:
            break
        chrome_js("window.scrollBy(0, Math.max(window.innerHeight * 2, 1400)); return true;", timeout=10)
        time.sleep(delay)
    return candidates


def extract_profile() -> dict[str, Any]:
    profile = chrome_js(
        r"""
        const text = (node) => node ? (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim() : '';
        const first = (selectors) => {
          for (const selector of selectors) {
            const value = text(document.querySelector(selector));
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
        const raw = (document.body.innerText || document.body.textContent || '').replace(/\s+/g, ' ').trim();
        const pathHandle = (location.pathname.match(/\/(@[^/?#]+)/) || [])[1] || '';
        const avatar = document.querySelector('img[alt][src]') || document.querySelector('img[src]');
        return {
          url: location.href.split('?')[0],
          handle: pathHandle,
          profile_title: first(['[data-e2e="user-title"]', 'h1']),
          display_name: first(['[data-e2e="user-subtitle"]', 'h2']),
          bio: first(['[data-e2e="user-bio"]', '[data-e2e*="bio"]']),
          followers_text: first(['strong[data-e2e="followers-count"]', '[data-e2e="followers-count"]']),
          following_text: first(['strong[data-e2e="following-count"]', '[data-e2e="following-count"]']),
          likes_text: first(['strong[data-e2e="likes-count"]', '[data-e2e="likes-count"]']),
          website: href(['a[data-e2e="user-link"]', 'a[href^="http"]:not([href*="tiktok.com"])']),
          avatar_url: avatar ? avatar.src : '',
          raw_text: raw.slice(0, 1800)
        };
        """,
        timeout=30,
    ) or {}

    raw = profile.get("raw_text", "")
    if not profile.get("followers_text"):
        match = re.search(r"([0-9][0-9,.]*\s*[KkMmBb万萬亿億千]?)\s*(粉丝|粉絲|Followers)", raw, re.I)
        if match:
            profile["followers_text"] = match.group(1).strip()
    if not profile.get("likes_text"):
        match = re.search(r"([0-9][0-9,.]*\s*[KkMmBb万萬亿億千]?)\s*(赞|Likes)", raw, re.I)
        if match:
            profile["likes_text"] = match.group(1).strip()

    profile["followers_count"] = parse_count(profile.get("followers_text"))
    profile["following_count"] = parse_count(profile.get("following_text"))
    profile["likes_count"] = parse_count(profile.get("likes_text"))
    return profile


def collect_influencers(args: argparse.Namespace) -> int:
    global TARGET_WINDOW_ID, TARGET_TAB_ID
    TARGET_WINDOW_ID, TARGET_TAB_ID = start_research_tab()
    run_dir = Path(args.output_dir) / f"{now_stamp()}_real_chrome_influencers"
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "real_chrome_influencers.json"
    csv_path = run_dir / "real_chrome_influencers.csv"
    rejected_path = run_dir / "real_chrome_rejected.csv"

    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}

    for keyword in args.keywords:
        print(f"[search] {keyword}", flush=True)
        queries = build_queries(keyword, args.use_variants)
        candidates = []
        seen_candidates: set[str] = set()
        for query in queries:
            if len(candidates) >= args.candidate_limit:
                break
            print(f"[query] {query}", flush=True)
            batch = scroll_search(
                query,
                max(1, args.candidate_limit - len(candidates)),
                args.search_scrolls,
                args.scroll_delay,
            )
            for item in batch:
                handle = item.get("handle")
                if handle and handle not in seen_candidates:
                    seen_candidates.add(handle)
                    candidates.append(item)
            if len(candidates) >= args.candidate_limit:
                break
        qualified = 0
        checked = 0

        for candidate in candidates:
            if qualified >= args.per_keyword:
                break
            checked += 1
            url = candidate["author_url"]
            try:
                chrome_set_url(url)
                loaded = wait_profile(candidate["handle"], timeout=args.profile_timeout)
                if candidate["handle"].lstrip("@").lower() not in (loaded.get("pathname") or "").lower():
                    print(f"[warn] navigation did not reach {url}: {loaded.get('url', '')}", file=sys.stderr, flush=True)
                    continue
                time.sleep(args.profile_delay)
                profile = extract_profile()
            except Exception as exc:
                print(f"[warn] {url} failed: {exc}", file=sys.stderr, flush=True)
                continue

            row = {
                "platform_keyword": keyword,
                "creator_url": profile.get("url") or url,
                "handle": profile.get("handle") or candidate.get("handle"),
                "profile_title": profile.get("profile_title", ""),
                "display_name": profile.get("display_name", ""),
                "bio": profile.get("bio", ""),
                "followers_text": profile.get("followers_text", ""),
                "followers_count": profile.get("followers_count"),
                "following_text": profile.get("following_text", ""),
                "following_count": profile.get("following_count"),
                "likes_text": profile.get("likes_text", ""),
                "likes_count": profile.get("likes_count"),
                "website": profile.get("website", ""),
                "avatar_url": profile.get("avatar_url", ""),
                "source_video_url": candidate.get("source_video_url", ""),
                "source_query": candidate.get("source_query", ""),
                "source_video_title": candidate.get("source_video_title", ""),
                "source_video_date": candidate.get("source_video_date", ""),
                "source_video_metric_1": candidate.get("source_video_metric_1", ""),
                "source_video_metric_2": candidate.get("source_video_metric_2", ""),
                "source_raw_text": candidate.get("source_raw_text", ""),
                "profile_raw_text": profile.get("raw_text", ""),
            }

            followers = row["followers_count"]
            if followers is not None and followers >= args.min_followers:
                rows.append(row)
                qualified += 1
                print(f"[ok] {keyword} {qualified}/{args.per_keyword} {row['handle']} {row['followers_text']}", flush=True)
            else:
                rejected.append(row)
                print(f"[skip] {keyword} {row['handle']} {row['followers_text']}", flush=True)
            write_progress(json_path, csv_path, rejected_path, args, summary, rows, rejected)
            time.sleep(args.profile_interval)

        summary[keyword] = {
            "candidate_count": len(candidates),
            "profiles_checked": checked,
            "qualified_count": qualified,
        }
        write_progress(json_path, csv_path, rejected_path, args, summary, rows, rejected)

    write_progress(json_path, csv_path, rejected_path, args, summary, rows, rejected)
    print(json.dumps({"ok": True, "run_dir": str(run_dir), "json": str(json_path), "csv": str(csv_path), "summary": summary}, ensure_ascii=False, indent=2))
    return 0


def write_progress(
    json_path: Path,
    csv_path: Path,
    rejected_path: Path,
    args: argparse.Namespace,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> None:
    payload = {
        "kind": "real-chrome-influencers",
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "keywords": args.keywords,
        "min_followers": args.min_followers,
        "per_keyword": args.per_keyword,
        "summary": summary,
        "items": rows,
        "rejected": rejected,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, rows)
    write_csv(rejected_path, rejected)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "platform_keyword",
        "creator_url",
        "handle",
        "profile_title",
        "display_name",
        "bio",
        "followers_text",
        "followers_count",
        "following_text",
        "following_count",
        "likes_text",
        "likes_count",
        "website",
        "avatar_url",
        "source_video_url",
        "source_query",
        "source_video_title",
        "source_video_date",
        "source_video_metric_1",
        "source_video_metric_2",
        "source_raw_text",
        "profile_raw_text",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TikTok research via the user's real Chrome and Apple Events.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    sub = parser.add_subparsers(dest="command", required=True)
    inf = sub.add_parser("influencers")
    inf.add_argument("keywords", nargs="+")
    inf.add_argument("--per-keyword", type=int, default=10)
    inf.add_argument("--min-followers", type=int, default=100_000)
    inf.add_argument("--candidate-limit", type=int, default=160)
    inf.add_argument("--search-scrolls", type=int, default=45)
    inf.add_argument("--scroll-delay", type=float, default=1.0)
    inf.add_argument("--profile-delay", type=float, default=3.0)
    inf.add_argument("--profile-timeout", type=int, default=20)
    inf.add_argument("--profile-interval", type=float, default=0.4)
    inf.add_argument("--no-variants", dest="use_variants", action="store_false")
    inf.set_defaults(use_variants=True)
    inf.set_defaults(func=collect_influencers)
    return parser


def build_queries(keyword: str, use_variants: bool) -> list[str]:
    if not use_variants:
        return [keyword]
    suffixes = [
        "",
        "haul",
        "tutorial",
        "review",
        "finds",
        "shipping",
        "agent",
        "discount",
        "coupon",
        "unboxing",
        "spreadsheet",
    ]
    return [keyword if not suffix else f"{keyword} {suffix}" for suffix in suffixes]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
