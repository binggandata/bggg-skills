#!/usr/bin/env python3
"""Build a bounded TikTok query plan for the built-in bggg-data-tiktok module."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def as_int(value: object, default: int, minimum: int, maximum: int, field: str) -> int:
    if value in (None, ""):
        return default
    number = int(str(value))
    if number < minimum or number > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return number


def build_plan(rows: list[dict], defaults: dict) -> dict:
    queries: list[dict] = []
    for idx, row in enumerate(rows, 1):
        query = str(row.get("query") or "").strip()
        if not query:
            raise ValueError(f"row {idx}: query is required")
        market = str(row.get("market") or defaults["market"]).strip()
        language = str(row.get("language") or defaults["language"]).strip()
        max_videos = as_int(row.get("max_videos"), defaults["max_videos"], 1, 500, "max_videos")
        max_comment_videos = as_int(row.get("max_comment_videos"), defaults["max_comment_videos"], 0, 20, "max_comment_videos")
        max_comments_per_video = as_int(row.get("max_comments_per_video"), defaults["max_comments_per_video"], 0, 500, "max_comments_per_video")
        plan_id = hashlib.sha256(f"{query}\x1f{market}\x1f{language}\x1f{idx}".encode()).hexdigest()[:12]
        queries.append({
            "plan_id": f"tt-{plan_id}", "query": query, "requested_market": market,
            "language": language, "search_url": f"https://www.tiktok.com/search?q={quote(query)}",
            "max_videos": max_videos, "max_comment_videos": max_comment_videos,
            "max_comments_per_video": max_comments_per_video,
            "sort_hint": str(row.get("sort") or "visible_default"),
        })
    return {
        "schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(), "queries": queries,
        "totals": {
            "queries": len(queries),
            "max_videos": sum(q["max_videos"] for q in queries),
            "max_comment_videos": sum(q["max_comment_videos"] for q in queries),
            "max_comments": sum(q["max_comment_videos"] * q["max_comments_per_video"] for q in queries),
        },
        "market_note": "requested_market is research intent; set observed_market from visible evidence or unknown",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--default-market", default="unspecified")
    parser.add_argument("--default-language", default="unspecified")
    parser.add_argument("--max-videos", type=int, default=10)
    parser.add_argument("--max-comment-videos", type=int, default=3)
    parser.add_argument("--max-comments-per-video", type=int, default=30)
    args = parser.parse_args()
    with Path(args.queries).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise SystemExit("Query file is empty.")
    defaults = {
        "market": args.default_market, "language": args.default_language, "max_videos": args.max_videos,
        "max_comment_videos": args.max_comment_videos, "max_comments_per_video": args.max_comments_per_video,
    }
    plan = build_plan(rows, defaults)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(plan["totals"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
