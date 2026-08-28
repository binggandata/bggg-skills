#!/usr/bin/env python3
"""Normalize explicitly labeled old Reddit visible-DOM packages."""

from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from bggg_data_reddit_normalize import EMPTY, compact, source_hash, text_hits


FULLNAME_RE = re.compile(r"^t[13]_[A-Za-z0-9]+$")


def expand_inputs(patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = [Path(value) for value in glob.glob(pattern)]
        if matches:
            paths.extend(matches)
        elif Path(pattern).exists():
            paths.append(Path(pattern))
    return sorted(dict.fromkeys(paths))


def load_keywords(path: str | None) -> list[str]:
    if not path:
        return []
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def absolute_url(value: object, fallback: object) -> str:
    url = str(value or "")
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return "https://old.reddit.com" + url
    return str(fallback or "")


def package_error(package: dict, requested_market: str = "") -> str | None:
    schema_version = package.get("schema_version")
    if schema_version == "visible-search-1.0":
        required = ("source_url", "query", "collected_at", "results")
    elif schema_version == "visible-dom-1.0":
        required = ("source_url", "query", "collected_at", "post", "items")
    else:
        return "invalid visible-DOM package"
    missing = [field for field in required if package.get(field) in (None, "")]
    if not package.get("requested_market") and not requested_market:
        missing.append("requested_market")
    if missing:
        return "missing required fields: " + ",".join(missing)
    if schema_version == "visible-search-1.0" and not isinstance(package.get("results"), list):
        return "invalid visible-search package"
    if schema_version == "visible-dom-1.0" and not isinstance(package.get("items"), list):
        return "invalid visible-dom package"
    if not str(package.get("source_url")).startswith("https://old.reddit.com/"):
        return "source_url must use old.reddit.com"
    if schema_version == "visible-dom-1.0":
        post_id = str((package.get("post") or {}).get("native_id") or "")
        if not post_id.startswith("t3_") or not FULLNAME_RE.fullmatch(post_id):
            return "invalid post native_id"
    return None


def package_context(package: dict, path: Path, requested_market: str, observed_market: str) -> dict:
    return {
        "collection_mode": "visible_dom",
        "requested_market": package.get("requested_market") or requested_market or None,
        "observed_market": package.get("observed_market") or observed_market or "unknown",
        "collected_at": package.get("collected_at"),
        "source_file": str(path),
        "source_url": package.get("source_url"),
        "stop_reason": package.get("stop_reason") or "visible_sample_saved",
        "json_route_status": package.get("json_route_status") or "not_used",
    }


def normalize(
    paths: list[Path],
    keywords: list[str],
    requested_market: str = "",
    observed_market: str = "",
) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    failures: list[dict] = []
    parent_counts: Counter[str] = Counter()
    skipped = 0

    for path in paths:
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append({"file": str(path), "error": str(exc)})
            continue
        validation_error = package_error(package, requested_market)
        if validation_error:
            failures.append({"file": str(path), "error": validation_error})
            continue

        query = str(package.get("query") or "")
        source_url = package.get("source_url")
        lang = str(package.get("lang") or "EN").upper()
        round_number = int(package.get("round") or 1)
        common_context = package_context(package, path, requested_market, observed_market)

        if package.get("schema_version") == "visible-search-1.0":
            for result_item in package.get("results") or []:
                raw_post_id = str(result_item.get("postId") or result_item.get("post_id") or "")
                post_id = raw_post_id if raw_post_id.startswith("t3_") else f"t3_{raw_post_id}"
                title = str(result_item.get("title") or "")
                body = str(result_item.get("body") or result_item.get("text") or "")
                post_text = "\n\n".join(
                    part for part in (title, body) if compact(part).casefold() not in EMPTY
                )
                if not FULLNAME_RE.fullmatch(post_id) or compact(post_text).casefold() in EMPTY:
                    skipped += 1
                    continue
                subreddit = str(result_item.get("subreddit") or "").strip()
                if subreddit and not subreddit.startswith("r/"):
                    subreddit = f"r/{subreddit}"
                url = absolute_url(result_item.get("url"), source_url)
                rows.append(
                    {
                        "platform": "Reddit",
                        "lang": lang,
                        "source_id": source_hash(post_id, post_text),
                        "native_id": post_id,
                        "date": result_item.get("date"),
                        "text_raw": post_text,
                        "engagement": {
                            "score": result_item.get("score"),
                            "num_comments": result_item.get("commentsText") or result_item.get("comments"),
                        },
                        "context": {
                            "content_type": "post",
                            **common_context,
                            "subreddit": subreddit or None,
                            "title": title,
                            "url": url,
                            "query": query,
                            "collection_role": "search_discovery",
                        },
                        "keyword_hit": text_hits(post_text, keywords, query),
                        "round": round_number,
                    }
                )
            continue

        post = package.get("post") or {}
        post_id = str(post.get("native_id") or "")
        post_text = "\n\n".join(
            part for part in (str(post.get("title") or ""), str(post.get("text") or ""))
            if compact(part).casefold() not in EMPTY
        )
        if post_id and compact(post_text).casefold() not in EMPTY:
            rows.append(
                {
                    "platform": "Reddit",
                    "lang": lang,
                    "source_id": source_hash(post_id, post_text),
                    "native_id": post_id,
                    "date": post.get("date"),
                    "text_raw": post_text,
                    "engagement": {"score": post.get("score"), "num_comments": post.get("comments")},
                    "context": {
                        "content_type": "post",
                        **common_context,
                        "subreddit": f"r/{post.get('subreddit')}" if post.get("subreddit") else None,
                        "title": post.get("title"),
                        "url": absolute_url(post.get("permalink"), source_url),
                        "query": query,
                    },
                    "keyword_hit": text_hits(post_text, keywords, query),
                    "round": round_number,
                }
            )

        for item in package["items"]:
            text = str(item.get("text") or "")
            native_id = str(item.get("native_id") or "").strip()
            if not native_id.startswith("t1_") or not FULLNAME_RE.fullmatch(native_id) or compact(text).casefold() in EMPTY:
                skipped += 1
                continue
            rows.append(
                {
                    "platform": "Reddit",
                    "lang": lang,
                    "source_id": source_hash(native_id, text),
                    "native_id": native_id,
                    "date": item.get("date"),
                    "text_raw": text,
                    "engagement": {"score": item.get("score")},
                    "context": {
                        "content_type": "comment",
                        **common_context,
                        "subreddit": f"r/{post.get('subreddit')}" if post.get("subreddit") else None,
                        "post_title": post.get("title"),
                        "post_id": post_id,
                        "parent_id": item.get("parent_native_id"),
                        "url": absolute_url(item.get("permalink"), source_url),
                        "query": query,
                        "is_reply": bool(item.get("is_reply")),
                        "author": item.get("author"),
                    },
                    "keyword_hit": text_hits(text, keywords, query),
                    "round": round_number,
                }
            )
    unique = {row["native_id"]: row for row in rows}
    result = sorted(unique.values(), key=lambda row: (str(row.get("date") or ""), row["native_id"]), reverse=True)
    parent_counts = Counter(
        str((row.get("context") or {}).get("post_id") or "unknown")
        for row in result
        if (row.get("context") or {}).get("content_type") == "comment"
    )
    summary = {
        "source_packages": len(paths),
        "package_failures": failures,
        "unique_rows": len(result),
        "unique_posts": sum(row["context"]["content_type"] == "post" for row in result),
        "unique_comments": sum(row["context"]["content_type"] == "comment" for row in result),
        "skipped_empty_or_invalid": skipped,
        "comment_rows_by_parent": dict(parent_counts.most_common()),
        "largest_parent_share": round(max(parent_counts.values()) / sum(parent_counts.values()), 4) if parent_counts else 0,
        "collection_mode": "visible_dom",
    }
    return result, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--keywords")
    parser.add_argument("--requested-market", default="")
    parser.add_argument("--observed-market", default="")
    args = parser.parse_args()

    paths = expand_inputs(args.inputs)
    if not paths:
        raise SystemExit("No visible-DOM packages matched.")
    rows, summary = normalize(
        paths,
        load_keywords(args.keywords),
        requested_market=args.requested_market,
        observed_market=args.observed_market,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if summary["package_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
