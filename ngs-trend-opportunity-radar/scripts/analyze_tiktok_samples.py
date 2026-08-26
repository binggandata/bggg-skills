#!/usr/bin/env python3
"""Compute deterministic TikTok sample gates from normalized rows and reviewed videos."""

from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_rows(patterns: list[str]) -> list[dict]:
    unique: dict[str, dict] = {}
    for pattern in patterns:
        for path_value in glob.glob(pattern):
            for line in Path(path_value).read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                key = str(row.get("source_id") or row.get("native_id") or "")
                if key:
                    unique.setdefault(key, row)
    return list(unique.values())


def load_relevance(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    required = {"source_id", "theme", "query_semantic_status"}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit("relevance TSV must contain source_id, theme, query_semantic_status")
    return {str(row["source_id"]): row for row in rows}


def analyze_rows(rows: list[dict], relevance: dict[str, dict]) -> dict:
    matched = {
        source_id: str(meta.get("theme") or "")
        for source_id, meta in relevance.items()
        if str(meta.get("query_semantic_status") or "").strip().casefold() in {"matched", "relevant"}
    }
    videos_by_theme: defaultdict[str, dict[str, dict]] = defaultdict(dict)
    native_to_theme: dict[str, str] = {}
    for row in rows:
        if str(row.get("content_type") or (row.get("context") or {}).get("content_type") or "") != "video":
            continue
        source_id = str(row.get("source_id") or "")
        theme = matched.get(source_id)
        if not theme:
            continue
        videos_by_theme[theme][source_id] = row
        native_id = str(row.get("native_id") or (row.get("context") or {}).get("parent_video_id") or "")
        if native_id:
            native_to_theme[native_id] = theme

    comments_by_theme: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if str(row.get("content_type") or (row.get("context") or {}).get("content_type") or "") != "comment":
            continue
        context = row.get("context") or {}
        parent_id = str(context.get("parent_video_id") or "")
        theme = native_to_theme.get(parent_id)
        if theme and str(row.get("text_raw") or "").strip():
            comments_by_theme[theme][parent_id] += 1

    results = {}
    for theme, videos in sorted(videos_by_theme.items()):
        accounts = {
            str((row.get("context") or {}).get("author_handle") or (row.get("context") or {}).get("author") or "").strip().casefold()
            for row in videos.values()
        } - {""}
        parent_counts = comments_by_theme[theme]
        comment_rows = sum(parent_counts.values())
        parent_videos = len(parent_counts)
        largest_share = round(max(parent_counts.values()) / comment_rows, 4) if comment_rows else 0
        relevant_videos = len(videos)
        quick_passed = relevant_videos >= 10 and len(accounts) >= 5
        deep_passed = relevant_videos >= 20 and parent_videos >= 5 and comment_rows >= 100
        results[theme] = {
            "status": "deep_passed" if deep_passed else "quick_passed" if quick_passed else "insufficient",
            "relevant_videos": relevant_videos,
            "accounts": len(accounts),
            "comment_parent_videos": parent_videos,
            "comment_rows": comment_rows,
            "largest_parent_share": largest_share,
            "concentration_warning": bool(comment_rows and largest_share > 0.4),
            "quick_gate_passed": quick_passed,
            "deep_gate_passed": deep_passed,
        }
    return {
        "normalized_unique_rows": len(rows),
        "reviewed_videos": len(relevance),
        "matched_videos": len(matched),
        "collected_matched_videos": sum(len(items) for items in videos_by_theme.values()),
        "themes": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--relevance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = analyze_rows(load_rows(args.inputs), load_relevance(args.relevance))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
