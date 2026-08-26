#!/usr/bin/env python3
"""Normalize immutable TikTok visible-DOM packages into auditable JSONL."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


COUNT_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([KMB万億亿]?)\s*$", re.I)
MULTIPLIERS = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "万": 10_000, "億": 100_000_000, "亿": 100_000_000}


def parse_count(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = COUNT_RE.match(str(value).replace(",", "").strip())
    if not match:
        return None
    return int(float(match.group(1)) * MULTIPLIERS[match.group(2).upper()])


def stable_id(*parts: object) -> str:
    payload = "\x1f".join("" if part is None else str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_id(item: dict, package: dict) -> str:
    content_type = str(item.get("content_type") or package.get("mode") or "unknown")
    native = str(item.get("native_id") or "").strip()
    if native:
        return stable_id("TikTok", content_type, native)
    url = item.get("url") or item.get("video_url") or package.get("source_url") or ""
    return stable_id("TikTok", content_type, url, item.get("author_handle"), item.get("text"), item.get("date_raw"))


def load_keywords(path: str | None) -> list[str]:
    if not path:
        return []
    return [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]


def expand_inputs(patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = [Path(p) for p in glob.glob(pattern)]
        if matches:
            paths.extend(matches)
        elif Path(pattern).exists():
            paths.append(Path(pattern))
    return sorted(dict.fromkeys(paths))


def normalize_item(item: dict, package: dict, source_file: Path, keywords: list[str]) -> dict | None:
    text_raw = str(item.get("text") or "")
    if not text_raw.strip():
        return None
    content_type = str(item.get("content_type") or ("video" if package.get("mode") == "discover" else "comment"))
    if content_type not in {"video", "comment"}:
        return None
    engagement = {key: parse_count(value) for key, value in (item.get("engagement") or {}).items()}
    url = item.get("url") or item.get("video_url") or package.get("source_url")
    context = {
        "query": package.get("query"), "requested_market": package.get("requested_market"),
        "observed_market": package.get("observed_market") or "unknown", "language": package.get("language"),
        "language_match": "not_checked", "query_semantic_status": "not_checked",
        "url": url, "video_url": item.get("video_url") or (url if content_type == "video" else package.get("source_url")),
        "rank_position": item.get("rank_position"), "collected_at": package.get("collected_at"),
        "source_file": str(source_file), "stop_reason": package.get("stop_reason"),
        "parent_video_id": item.get("parent_video_id"), "parent_comment_id": item.get("parent_comment_id"),
        "is_reply": bool(item.get("is_reply")), "author_handle": item.get("author_handle"),
        "collection_mode": "visible_dom_cdp",
    }
    folded = text_raw.casefold()
    hits = [keyword for keyword in keywords if keyword.casefold() in folded]
    return {
        "platform": "TikTok", "content_type": content_type, "source_id": source_id(item, package),
        "native_id": item.get("native_id") or None, "date": item.get("published_at") or None,
        "date_raw": item.get("date_raw") or None, "observed_at": package.get("collected_at"),
        "text_raw": text_raw, "engagement": engagement, "context": context, "keyword_hit": hits,
    }


def normalize_packages(paths: list[Path], keywords: list[str]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    failures: list[dict] = []
    stop_reasons, requested_markets, observed_markets = Counter(), Counter(), Counter()
    input_items = skipped_empty = 0
    for path in paths:
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append({"file": str(path), "error": str(exc)})
            continue
        if package.get("mode") not in {"discover", "comments"} or not isinstance(package.get("items"), list):
            failures.append({"file": str(path), "error": "invalid mode or items"})
            continue
        stop_reasons[str(package.get("stop_reason") or "unknown")] += 1
        requested_markets[str(package.get("requested_market") or "unspecified")] += 1
        observed_markets[str(package.get("observed_market") or "unknown")] += 1
        for item in package["items"]:
            input_items += 1
            row = normalize_item(item, package, path, keywords)
            if row is None:
                skipped_empty += 1
            else:
                rows.append(row)
    unique: dict[str, dict] = {}
    duplicates = 0
    for row in rows:
        if row["source_id"] in unique:
            duplicates += 1
        else:
            unique[row["source_id"]] = row
    rows = sorted(unique.values(), key=lambda row: (str(row["content_type"]), str(row.get("date") or ""), row["source_id"]))
    dates = [str(row["date"]) for row in rows if row.get("date")]
    summary = {
        "source_packages": len(paths), "input_items": input_items, "unique_rows": len(rows),
        "video_rows": sum(row["content_type"] == "video" for row in rows),
        "comment_rows": sum(row["content_type"] == "comment" for row in rows),
        "reply_rows": sum(row["content_type"] == "comment" and row["context"].get("is_reply") for row in rows),
        "duplicates": duplicates, "skipped_empty_or_invalid_items": skipped_empty,
        "missing_url": sum(not row["context"].get("url") for row in rows),
        "missing_date": sum(not row.get("date") and not row.get("date_raw") for row in rows),
        "earliest_date": min(dates) if dates else None, "latest_date": max(dates) if dates else None,
        "requested_markets": dict(requested_markets), "observed_markets": dict(observed_markets),
        "stop_reasons": dict(stop_reasons), "package_failures": failures,
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--keywords")
    args = parser.parse_args()
    paths = expand_inputs(args.inputs)
    if not paths:
        raise SystemExit("No source packages matched.")
    rows, summary = normalize_packages(paths, load_keywords(args.keywords))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if summary["package_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
