#!/usr/bin/env python3
"""Normalize saved Reddit search/comment JSON into auditable JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


EMPTY = {"", "[deleted]", "[removed]"}


def compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def source_hash(native_id: str, text: str) -> str:
    return hashlib.sha256(f"{native_id}\n{text}".encode("utf-8")).hexdigest()[:24]


def iso_date(value: Any) -> str | None:
    try:
        return (
            datetime.fromtimestamp(float(value), tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    except (TypeError, ValueError, OSError):
        return None


def text_hits(text: str, keywords: list[str], query: str) -> list[str]:
    lowered = text.casefold()
    hits = [word for word in keywords if word.casefold() in lowered]
    if query and query.casefold() in lowered and query not in hits:
        hits.append(query)
    return hits


def walk_things(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, list):
        for item in node:
            yield from walk_things(item)
        return
    if not isinstance(node, dict):
        return
    kind = node.get("kind")
    data = node.get("data")
    if kind in {"t1", "t3", "more"} and isinstance(data, dict):
        yield node
    if isinstance(data, dict):
        yield from walk_things(data.get("children"))
        replies = data.get("replies")
        if isinstance(replies, dict):
            yield from walk_things(replies)


def read_manifest(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if "file" not in row and "path" not in row:
            raise SystemExit(f"manifest line {line_number}: missing file/path")
        rows.append(row)
    return rows


def post_row(data: dict, meta: dict, keywords: list[str]) -> dict | None:
    if data.get("promoted") or data.get("is_created_from_ads_ui"):
        return None
    title = str(data.get("title") or "")
    body = str(data.get("selftext") or "")
    text = "\n\n".join(part for part in (title, body) if compact(part).casefold() not in EMPTY)
    if compact(text).casefold() in EMPTY:
        return None
    native_id = str(data.get("name") or f"t3_{data.get('id') or ''}").strip()
    permalink = str(data.get("permalink") or "")
    url = "https://www.reddit.com" + permalink if permalink.startswith("/") else permalink
    query = str(meta.get("query") or "")
    return {
        "platform": "Reddit",
        "lang": str(meta.get("lang") or "EN").upper(),
        "source_id": source_hash(native_id, text),
        "native_id": native_id,
        "date": iso_date(data.get("created_utc")),
        "text_raw": text,
        "engagement": {
            "score": data.get("score"),
            "num_comments": data.get("num_comments"),
            "upvote_ratio": data.get("upvote_ratio"),
        },
        "context": {
            "content_type": "post",
            "collection_mode": meta.get("source_route") or "reddit_json_api",
            "subreddit": f"r/{data.get('subreddit')}" if data.get("subreddit") else None,
            "title": title,
            "url": url,
            "query": query,
            "requested_market": meta.get("requested_market"),
            "observed_market": meta.get("observed_market") or "unknown",
            "collected_at": meta.get("collected_at"),
            "source_file": str(meta["_resolved_file"]),
            "source_url": meta.get("url"),
        },
        "keyword_hit": text_hits(text, keywords, query),
        "round": int(meta.get("round") or 1),
    }


def comment_row(data: dict, meta: dict, root: dict, keywords: list[str]) -> dict | None:
    body = str(data.get("body") or "")
    if compact(body).casefold() in EMPTY:
        return None
    native_id = str(data.get("name") or f"t1_{data.get('id') or ''}").strip()
    permalink = str(data.get("permalink") or "")
    url = "https://www.reddit.com" + permalink if permalink.startswith("/") else permalink
    query = str(meta.get("query") or "")
    return {
        "platform": "Reddit",
        "lang": str(meta.get("lang") or "EN").upper(),
        "source_id": source_hash(native_id, body),
        "native_id": native_id,
        "date": iso_date(data.get("created_utc")),
        "text_raw": body,
        "engagement": {"score": data.get("score")},
        "context": {
            "content_type": "comment",
            "collection_mode": meta.get("source_route") or "reddit_json_api",
            "subreddit": (
                f"r/{data.get('subreddit')}" if data.get("subreddit") else root.get("subreddit")
            ),
            "post_title": root.get("title"),
            "post_id": root.get("name"),
            "parent_id": data.get("parent_id"),
            "url": url,
            "query": query,
            "requested_market": meta.get("requested_market"),
            "observed_market": meta.get("observed_market") or "unknown",
            "collected_at": meta.get("collected_at"),
            "source_file": str(meta["_resolved_file"]),
            "source_url": meta.get("url"),
        },
        "keyword_hit": text_hits(body, keywords, query),
        "round": int(meta.get("round") or 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--keywords", type=Path)
    args = parser.parse_args()

    keywords = []
    if args.keywords:
        keywords = [
            line.strip()
            for line in args.keywords.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    unique: dict[str, dict] = {}
    stats = Counter()
    parent_counts = Counter()
    for meta in read_manifest(args.manifest):
        file_path = Path(meta.get("file") or meta.get("path"))
        if not file_path.is_absolute():
            file_path = (args.manifest.parent / file_path).resolve()
        meta = {**meta, "_resolved_file": file_path}
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            stats["invalid_source_files"] += 1
            continue
        stats["source_files"] += 1
        kind = str(meta.get("kind") or ("comments" if isinstance(payload, list) else "search"))
        if kind == "search":
            for thing in walk_things(payload):
                if thing.get("kind") != "t3":
                    continue
                row = post_row(thing["data"], meta, keywords)
                if row is None:
                    stats["posts_skipped"] += 1
                    continue
                stats["posts_seen"] += 1
                unique.setdefault(row["native_id"], row)
        else:
            root = {}
            if isinstance(payload, list) and payload:
                for thing in walk_things(payload[0]):
                    if thing.get("kind") == "t3":
                        root_data = thing["data"]
                        root = {
                            "name": root_data.get("name") or f"t3_{root_data.get('id') or ''}",
                            "title": root_data.get("title"),
                            "subreddit": (
                                f"r/{root_data.get('subreddit')}"
                                if root_data.get("subreddit")
                                else None
                            ),
                        }
                        break
            comment_payload = payload[1:] if isinstance(payload, list) else payload
            for thing in walk_things(comment_payload):
                if thing.get("kind") == "more":
                    stats["unresolved_more_nodes"] += 1
                    continue
                if thing.get("kind") != "t1":
                    continue
                row = comment_row(thing["data"], meta, root, keywords)
                if row is None:
                    stats["comments_skipped"] += 1
                    continue
                stats["comments_seen"] += 1
                unique.setdefault(row["native_id"], row)
    rows = sorted(
        unique.values(),
        key=lambda row: ((row.get("date") or ""), row["native_id"]),
        reverse=True,
    )
    parent_counts = Counter(
        str(row["context"].get("post_id") or "unknown")
        for row in rows
        if row["context"]["content_type"] == "comment"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = {
        **dict(stats),
        "unique_rows": len(rows),
        "unique_posts": sum(row["context"]["content_type"] == "post" for row in rows),
        "unique_comments": sum(row["context"]["content_type"] == "comment" for row in rows),
        "duplicate_native_ids": stats["posts_seen"] + stats["comments_seen"] - len(rows),
        "comment_rows_by_parent": dict(parent_counts.most_common()),
        "largest_parent_share": (
            round(max(parent_counts.values()) / sum(parent_counts.values()), 4)
            if parent_counts
            else 0
        ),
        "output": str(args.output),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
