#!/usr/bin/env python3
"""Built-in bggg-data-tiktok collector for visible videos and comments."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - live dependency
    sync_playwright = None


DEFAULT_CDP = "http://127.0.0.1:9222"


VIDEO_EXTRACTOR = r"""
() => {
  const rows = [], seen = new Set();
  for (const link of document.querySelectorAll('a[href*="/video/"]')) {
    const href = link.href || link.getAttribute('href') || '';
    const match = href.match(/\/@([^/]+)\/video\/(\d+)/);
    if (!match || seen.has(match[2])) continue;
    seen.add(match[2]);
    const card = link.closest('[data-e2e="search-video-card"]') ||
      link.closest('[data-e2e*="user-post-item"]') || link.closest('div') || link;
    const raw = (card.innerText || card.textContent || '').replace(/\s+/g, ' ').trim();
    const titleNode = card.querySelector('[data-e2e="video-desc"], [data-e2e="video-title"]');
    const strong = [...card.querySelectorAll('strong')].map(n => (n.textContent || '').trim()).filter(Boolean);
    rows.push({
      url: href.split('?')[0], video_id: match[2], author: '@' + match[1],
      text: ((titleNode && titleNode.textContent) || raw).trim().slice(0, 2000),
      raw_text: raw.slice(0, 4000), metrics: strong.slice(0, 4)
    });
  }
  return rows;
}
"""


COMMENT_EXTRACTOR = r"""
() => {
  const selectors = [
    '[data-e2e="comment-level-1"]', '[data-e2e="comment-level-2"]',
    '[data-e2e*="comment-item"]', 'div[class*="DivCommentItemContainer"]'
  ];
  const nodes = [...new Set(selectors.flatMap(s => [...document.querySelectorAll(s)]))];
  return nodes.map((node, index) => {
    const raw = (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim();
    const authorNode = node.querySelector('a[href*="/@"], [data-e2e*="comment-username"]');
    const authorHref = authorNode && (authorNode.href || authorNode.getAttribute('href')) || '';
    const authorMatch = authorHref.match(/\/@([^/?#]+)/);
    const id = node.getAttribute('data-id') || node.id || '';
    return {comment_id: id, author: authorMatch ? '@' + authorMatch[1] : '', text: raw.slice(0, 6000), index};
  }).filter(row => row.text);
}
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def normalize_url(value: str) -> str:
    value = value.strip()
    if value.startswith("/"):
        value = "https://www.tiktok.com" + value
    return value.split("?")[0]


def parse_metric(value: str) -> int | None:
    text = str(value or "").replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*([KkMmBb万萬千]?)", text)
    if not match:
        return None
    multiplier = {"": 1, "K": 1_000, "k": 1_000, "M": 1_000_000, "m": 1_000_000,
                  "B": 1_000_000_000, "b": 1_000_000_000, "千": 1_000,
                  "万": 10_000, "萬": 10_000}[match.group(2)]
    return int(float(match.group(1)) * multiplier)


def check_cdp(endpoint: str) -> dict[str, Any]:
    with urllib.request.urlopen(endpoint.rstrip("/") + "/json/version", timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def connect(endpoint: str):
    if sync_playwright is None:
        raise RuntimeError("Missing dependency: playwright. Install with `python3 -m pip install playwright`.")
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(endpoint)
    except Exception:
        playwright.stop()
        raise
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(15_000)
    return playwright, page


def wait_page(page) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
    except Exception:
        pass
    page.wait_for_timeout(1_500)


def scroll_collect(page, extractor: str, limit: int, max_scrolls: int) -> tuple[list[dict], str]:
    rows, seen = [], set()
    stable = 0
    for _ in range(max_scrolls + 1):
        batch = page.evaluate(extractor)
        before = len(rows)
        for row in batch:
            key = row.get("video_id") or row.get("comment_id") or stable_id(row.get("author", ""), row.get("text", ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            if len(rows) >= limit:
                return rows[:limit], "sample_cap"
        stable = stable + 1 if len(rows) == before else 0
        if stable >= 3 and rows:
            return rows[:limit], "stable_no_new"
        page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 1.8, 1000))")
        page.wait_for_timeout(1_200)
    return rows[:limit], "scroll_cap"


def context(args, source_file: Path, collected_at: str, **extra) -> dict:
    return {
        "query": getattr(args, "query", None),
        "requested_market": args.requested_market,
        "observed_market": "unknown",
        "language": args.language,
        "language_match": "not_checked",
        "query_semantic_status": "not_checked",
        "collection_mode": "visible_dom_cdp",
        "collected_at": collected_at,
        "source_file": str(source_file),
        **extra,
    }


def video_rows(items: list[dict], args, source_file: Path, observed_at: str) -> list[dict]:
    rows = []
    for item in items:
        url = normalize_url(item.get("url", ""))
        native_id = str(item.get("video_id") or "") or None
        source_id = stable_id("TikTok", "video", native_id) if native_id else stable_id("TikTok", "video", url, item.get("author", ""), item.get("text", ""), "")
        metrics = item.get("metrics") or []
        rows.append({
            "platform": "TikTok", "content_type": "video", "source_id": source_id,
            "native_id": native_id, "date": None, "observed_at": observed_at,
            "text_raw": item.get("text") or item.get("raw_text") or "",
            "engagement": {"views": parse_metric(metrics[0]) if metrics else None, "likes": None, "comments": None},
            "context": context(args, source_file, observed_at, url=url, parent_video_id=native_id, author=item.get("author")),
        })
    return rows


def comment_rows(items: list[dict], args, video_url: str, parent_id: str, source_file: Path, observed_at: str) -> list[dict]:
    rows = []
    for item in items:
        text = item.get("text") or ""
        native_id = str(item.get("comment_id") or "") or None
        source_id = stable_id("TikTok", "comment", native_id) if native_id else stable_id("TikTok", "comment", video_url, item.get("author", ""), text, "")
        rows.append({
            "platform": "TikTok", "content_type": "comment", "source_id": source_id,
            "native_id": native_id, "date": None, "observed_at": observed_at, "text_raw": text,
            "engagement": {"likes": None},
            "context": context(args, source_file, observed_at, url=video_url, video_url=video_url, parent_video_id=parent_id, author=item.get("author")),
        })
    return rows


def write_rows(path: Path, rows: list[dict], append: bool) -> int:
    existing = []
    if append and path.exists():
        existing = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    merged = {str(row.get("source_id")): row for row in existing + rows if row.get("source_id")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in merged.values()), encoding="utf-8")
    return len(merged)


def tiktok_work_dir(output: Path) -> Path:
    try:
        run_dir = output.resolve().parents[2]
    except IndexError as exc:
        raise ValueError("output must be inside <run>/data/raw/") from exc
    return run_dir / "work" / "tiktok"


def save_source_package(args, mode: str, identity: str, source_url: str, items: list[dict], stop_reason: str, collected_at: str) -> Path:
    work_dir = tiktok_work_dir(Path(args.output))
    source_dir = work_dir / "source_json"
    source_dir.mkdir(parents=True, exist_ok=True)
    prefix = "query" if mode == "discover" else "video"
    stem = f"{prefix}_{stable_id(identity)[:12]}"
    attempt = len(list(source_dir.glob(f"{stem}_attempt_*.json"))) + 1
    path = source_dir / f"{stem}_attempt_{attempt:02d}.json"
    package = {
        "schema_version": "1.0", "mode": mode, "query": getattr(args, "query", None),
        "requested_market": args.requested_market, "observed_market": "unknown", "language": args.language,
        "source_url": source_url, "collected_at": collected_at, "stop_reason": stop_reason, "items": items,
    }
    path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "file": str(path), "mode": mode, "source_url": source_url, "items": len(items),
        "collected_at": collected_at, "stop_reason": stop_reason, "success": True,
    }
    with (work_dir / "source_manifest.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False) + "\n")
    return path


def log_failure(args, error: Exception) -> None:
    if not getattr(args, "output", None):
        return
    work_dir = tiktok_work_dir(Path(args.output))
    work_dir.mkdir(parents=True, exist_ok=True)
    row = {"command": args.command, "collected_at": now_iso(), "error": str(error), "success": False}
    with (work_dir / "failure_log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def screenshot(page, folder: str, label: str) -> str:
    if not folder:
        return ""
    target = Path(folder) / f"{re.sub(r'[^A-Za-z0-9._-]+', '_', label)[:80]}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(target), full_page=False)
    return str(target)


def command_search(args) -> int:
    playwright, page = connect(args.cdp)
    try:
        url = "https://www.tiktok.com/search/video?q=" + urllib.parse.quote(args.query.lstrip("#"))
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        wait_page(page)
        items, stop_reason = scroll_collect(page, VIDEO_EXTRACTOR, args.limit, args.max_scrolls)
        collected_at = now_iso()
        package_items = []
        for rank, item in enumerate(items, 1):
            metrics = item.get("metrics") or []
            package_items.append({
                "content_type": "video", "native_id": item.get("video_id"), "url": normalize_url(item.get("url", "")),
                "text": item.get("text") or item.get("raw_text") or "", "author_handle": str(item.get("author") or "").lstrip("@"),
                "published_at": None, "date_raw": None, "rank_position": rank,
                "engagement": {"views": metrics[0] if metrics else None, "likes": None, "comments": None},
            })
        source_file = save_source_package(args, "discover", args.query, url, package_items, stop_reason, collected_at)
        shot = screenshot(page, args.screenshot_dir, "search_" + args.query)
        total = write_rows(Path(args.output), video_rows(items, args, source_file, collected_at), args.append)
        print(json.dumps({"ok": True, "collected": len(items), "total_rows": total, "source_package": str(source_file), "stop_reason": stop_reason, "screenshot": shot}, ensure_ascii=False))
        return 0
    finally:
        playwright.stop()


def video_id(url: str) -> str:
    match = re.search(r"/video/(\d+)", url)
    return match.group(1) if match else stable_id(normalize_url(url))


def command_comments(args) -> int:
    playwright, page = connect(args.cdp)
    collected, shots = [], []
    try:
        for url in args.video_url:
            clean_url = normalize_url(url)
            parent_id = video_id(clean_url)
            page.goto(clean_url, wait_until="domcontentloaded", timeout=60_000)
            wait_page(page)
            items, stop_reason = scroll_collect(page, COMMENT_EXTRACTOR, args.limit_per_video, args.max_scrolls)
            collected_at = now_iso()
            package_items = [{
                "content_type": "comment", "native_id": item.get("comment_id") or None,
                "parent_video_id": parent_id, "parent_comment_id": None, "video_url": clean_url, "url": clean_url,
                "text": item.get("text") or "", "author_handle": str(item.get("author") or "").lstrip("@"),
                "published_at": None, "date_raw": None, "is_reply": False, "engagement": {"likes": None},
            } for item in items]
            source_file = save_source_package(args, "comments", parent_id, clean_url, package_items, stop_reason, collected_at)
            collected.extend(comment_rows(items, args, clean_url, parent_id, source_file, collected_at))
            shots.append(screenshot(page, args.screenshot_dir, "comments_" + parent_id))
        total = write_rows(Path(args.output), collected, args.append)
        print(json.dumps({"ok": True, "collected": len(collected), "parents": len(args.video_url), "total_rows": total, "screenshots": shots}, ensure_ascii=False))
        return 0
    finally:
        playwright.stop()


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--requested-market", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--screenshot-dir", default="")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--max-scrolls", type=int, default=18)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp", default=DEFAULT_CDP)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.set_defaults(func=lambda args: print(json.dumps({"ok": True, "browser": check_cdp(args.cdp)}, ensure_ascii=False)) or 0)
    search = sub.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=30)
    add_common(search)
    search.set_defaults(func=command_search)
    comments = sub.add_parser("comments")
    comments.add_argument("--video-url", nargs="+", required=True)
    comments.add_argument("--limit-per-video", type=int, default=40)
    add_common(comments)
    comments.set_defaults(func=command_comments)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        log_failure(args, exc)
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
