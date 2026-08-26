#!/usr/bin/env python3
"""Compute deterministic Reddit sample gates from normalized rows and reviewed parents."""

from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path


def route_priority(row: dict) -> int:
    mode = str((row.get("context") or {}).get("collection_mode") or "")
    return 1 if mode == "visible_dom" else 2


def load_rows(patterns: list[str]) -> list[dict]:
    paths = sorted({Path(value) for pattern in patterns for value in glob.glob(pattern)})
    unique: dict[str, dict] = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = str(row.get("native_id") or row.get("source_id") or "")
            if not key:
                continue
            if key not in unique or route_priority(row) > route_priority(unique[key]):
                unique[key] = row
    return list(unique.values())


def load_relevance(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    required = {"native_id", "theme", "query_semantic_status"}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit("relevance TSV must contain native_id, theme, query_semantic_status")
    return {str(row["native_id"]): row for row in rows}


def analyze_rows(rows: list[dict], relevance: dict[str, dict]) -> dict:
    matched_parents: dict[str, str] = {
        native_id: str(meta.get("theme") or "")
        for native_id, meta in relevance.items()
        if str(meta.get("query_semantic_status") or "").lower() in {"matched", "relevant"}
    }
    relevant_posts: defaultdict[str, set[str]] = defaultdict(set)
    comments_by_theme: defaultdict[str, Counter[str]] = defaultdict(Counter)
    modes_by_theme: defaultdict[str, set[str]] = defaultdict(set)

    for row in rows:
        context = row.get("context") or {}
        content_type = context.get("content_type") or row.get("content_type")
        native_id = str(row.get("native_id") or "")
        if content_type == "post" and native_id in matched_parents:
            theme = matched_parents[native_id]
            relevant_posts[theme].add(native_id)
            modes_by_theme[theme].add(str(context.get("collection_mode") or "unknown"))

    collected_parent_theme = {
        parent_id: theme
        for theme, parent_ids in relevant_posts.items()
        for parent_id in parent_ids
    }
    for row in rows:
        context = row.get("context") or {}
        content_type = context.get("content_type") or row.get("content_type")
        if content_type != "comment" or not str(row.get("text_raw") or "").strip():
            continue
        post_id = str(context.get("post_id") or "")
        theme = collected_parent_theme.get(post_id)
        if not theme:
            continue
        comments_by_theme[theme][post_id] += 1
        modes_by_theme[theme].add(str(context.get("collection_mode") or "unknown"))

    themes = sorted(relevant_posts)
    results = {}
    for theme in themes:
        parent_counts = comments_by_theme[theme]
        comments = sum(parent_counts.values())
        comment_parents = len(parent_counts)
        posts = len(relevant_posts[theme])
        largest_share = round(max(parent_counts.values()) / comments, 4) if comments else 0
        quick_passed = posts >= 10
        deep_passed = posts >= 10 and comment_parents >= 5 and comments >= 100
        results[theme] = {
            "status": "deep_passed" if deep_passed else "quick_passed" if quick_passed else "insufficient",
            "relevant_posts": posts,
            "parent_posts": posts,
            "comment_parent_posts": comment_parents,
            "comment_rows": comments,
            "largest_parent_share": largest_share,
            "concentration_warning": bool(comments and largest_share > 0.4),
            "collection_modes": sorted(modes_by_theme[theme]),
            "quick_gate_passed": quick_passed,
            "deep_gate_passed": deep_passed,
        }
    return {
        "normalized_unique_rows": len(rows),
        "reviewed_parent_posts": len(relevance),
        "matched_parent_posts": len(matched_parents),
        "collected_matched_parent_posts": sum(len(ids) for ids in relevant_posts.values()),
        "themes": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--relevance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = load_rows(args.inputs)
    relevance = load_relevance(args.relevance)
    payload = analyze_rows(rows, relevance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
