#!/usr/bin/env python3
"""Export channel-separated staging CSVs used to build one audit workbook."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_jsonl_files(paths: list[Path]) -> list[dict]:
    rows: dict[str, dict] = {}
    for path in paths:
        for row in load_jsonl(path):
            is_reddit = str(row.get("platform") or "").lower() == "reddit"
            key = str(row.get("native_id") if is_reddit else row.get("source_id") or "")
            if not key:
                continue
            existing = rows.get(key)
            if not existing:
                rows[key] = row
                continue
            current_mode = str((row.get("context") or {}).get("collection_mode") or "")
            existing_mode = str((existing.get("context") or {}).get("collection_mode") or "")
            if is_reddit and existing_mode == "visible_dom" and current_mode != "visible_dom":
                chosen, duplicate = row, existing
                rows[key] = chosen
            else:
                chosen, duplicate = existing, row
            chosen_context = chosen.setdefault("context", {})
            alternate = set(chosen_context.get("alternate_source_files") or [])
            for candidate in (duplicate, chosen):
                source_file = (candidate.get("context") or {}).get("source_file")
                if source_file and source_file != chosen_context.get("source_file"):
                    alternate.add(str(source_file))
            if alternate:
                chosen_context["alternate_source_files"] = sorted(alternate)
    return list(rows.values())


def latest_file(folder: Path, pattern: str, *, exclude_prefixes: tuple[str, ...] = ()) -> Path | None:
    files = [path for path in folder.glob(pattern) if not any(path.name.startswith(prefix) for prefix in exclude_prefixes)]
    return sorted(files)[-1] if files else None


def newest_snapshot(folder: Path, pattern: str) -> Path | None:
    files = list(folder.glob(pattern))
    return max(files, key=lambda path: path.stat().st_mtime_ns) if files else None


def selected_normalized_files(run: Path, platform: str) -> list[Path]:
    raw = run / "data" / "raw"
    if platform == "tiktok":
        latest = newest_snapshot(raw, "tiktok_*.jsonl")
        return [latest] if latest else []
    visible = newest_snapshot(raw, "reddit_visible_*.jsonl")
    if visible:
        return [visible]
    latest = newest_snapshot(raw, "reddit*.jsonl")
    return [latest] if latest else []


def load_sorftime_products(paths: list[Path], run: Path) -> list[dict]:
    products: dict[str, dict] = {}
    anonymous = 0
    for file in sorted(paths):
        payload = load_json(file, {}) or {}
        for row in payload.get("data") or []:
            asin = str(row.get("asin") or "").strip().upper()
            key = asin or f"__anonymous_{anonymous}"
            if not asin:
                anonymous += 1
            source_file = str(file.relative_to(run))
            if key not in products:
                products[key] = {**row, "asin": asin or row.get("asin"), "source_file": source_file}
            else:
                existing = products[key]
                for field, value in row.items():
                    if existing.get(field) in (None, "", []) and value not in (None, "", []):
                        existing[field] = value
                source_files = set(str(existing.get("source_file") or "").split(" | "))
                source_files.add(source_file)
                existing["source_file"] = " | ".join(sorted(value for value in source_files if value))
    return [{"rank": rank, **row} for rank, row in enumerate(products.values(), 1)]


def sorftime_product_files(run: Path) -> list[Path]:
    paths = set((run / "sorftime").glob("*products*.json"))
    for call in load_jsonl(run / "sorftime" / "call_log.jsonl"):
        tool = str(call.get("tool") or "").strip().rsplit("/", 1)[-1].rsplit(".", 1)[-1]
        response_file = call.get("response_file")
        if tool != "product_search" or call.get("success") is False or not response_file:
            continue
        path = Path(str(response_file))
        path = path if path.is_absolute() else run / path
        if path.exists():
            paths.add(path)
    return sorted(paths)


def scalar(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fields:
        fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: scalar(row.get(key)) for key in fields})


def flatten_content(row: dict) -> dict:
    context = row.get("context") or {}
    engagement = row.get("engagement") or {}
    return {
        "platform": row.get("platform"),
        "content_type": row.get("content_type") or context.get("content_type"),
        "source_id": row.get("source_id"),
        "native_id": row.get("native_id"),
        "date": row.get("date"),
        "date_raw": row.get("date_raw"),
        "collected_at": row.get("observed_at") or context.get("collected_at"),
        "text_raw": row.get("text_raw"),
        "stars": engagement.get("stars"),
        "likes_or_score": engagement.get("likes") if engagement.get("likes") is not None else engagement.get("score"),
        "views": engagement.get("views"),
        "comments": engagement.get("comments") or engagement.get("num_comments"),
        "verified": engagement.get("verified"),
        "query": context.get("query"),
        "requested_market": context.get("requested_market"),
        "observed_market": context.get("observed_market"),
        "language": context.get("language") or row.get("lang"),
        "language_match": context.get("language_match"),
        "query_semantic_status": context.get("query_semantic_status") or row.get("query_semantic_status"),
        "parent_id": context.get("parent_video_id") or context.get("post_id"),
        "asins": context.get("asins"),
        "url": context.get("url") or context.get("video_url") or (f"https://www.amazon.com/dp/{context.get('asins',[None])[0]}" if context.get("asins") else None),
        "source_file": context.get("source_file"),
        "collection_mode": context.get("collection_mode") or context.get("source_route"),
    }


def fields_with_rows(base: list[str], rows: list[dict]) -> list[str]:
    return list(dict.fromkeys(base + [key for row in rows for key in row]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run = Path(args.run_dir)
    out = run / "work" / "workbook-sources"
    for legacy_name in (
        "04_sorftime_categories.csv",
        "05_sorftime_products.csv",
        "06_amazon_reviews.csv",
        "07_evidence_index.csv",
    ):
        legacy_path = out / legacy_name
        if legacy_path.exists():
            legacy_path.unlink()

    trends_file = latest_file(run / "work" / "google-trends", "*.json")
    tiktok_files = selected_normalized_files(run, "tiktok")
    reddit_files = selected_normalized_files(run, "reddit")
    trends_raw = load_json(trends_file, {}) if trends_file else {}
    trend_rows = []
    for series in trends_raw.get("series") or []:
        for point in series.get("values") or []:
            trend_rows.append(
                {
                    "theme": series.get("name"),
                    "date": point.get("date"),
                    "relative_search_interest": point.get("value"),
                    "requested_market": trends_raw.get("requested_market"),
                    "observed_market": trends_raw.get("observed_market"),
                    "source_url": trends_raw.get("source_url"),
                    "collected_at": trends_raw.get("collected_at"),
                    "source_file": str(trends_file.relative_to(run)) if trends_file else None,
                }
            )
    trend_fields = ["theme", "date", "relative_search_interest", "requested_market", "observed_market", "source_url", "collected_at", "source_file"]
    write_csv(out / "01_google_trends.csv", trend_rows, fields_with_rows(trend_fields, trend_rows))

    tiktok = load_jsonl_files(tiktok_files)
    content_fields = list(flatten_content({}).keys())
    tiktok_videos = [flatten_content(row) for row in tiktok if row.get("content_type") == "video"]
    tiktok_comments = [flatten_content(row) for row in tiktok if row.get("content_type") in {"comment", "reply"}]
    write_csv(out / "02_tiktok_videos.csv", tiktok_videos, fields_with_rows(content_fields, tiktok_videos))
    write_csv(out / "03_tiktok_comments.csv", tiktok_comments, fields_with_rows(content_fields, tiktok_comments))

    reddit = load_jsonl_files(reddit_files)
    reddit_posts = [flatten_content(row) for row in reddit if (row.get("context") or {}).get("content_type") == "post"]
    reddit_comments = [flatten_content(row) for row in reddit if (row.get("context") or {}).get("content_type") == "comment"]
    write_csv(out / "04_reddit_posts.csv", reddit_posts, fields_with_rows(content_fields, reddit_posts))
    write_csv(out / "05_reddit_comments.csv", reddit_comments, fields_with_rows(content_fields, reddit_comments))

    pool = load_json(run / "analysis" / "opportunity_pool.json", {}) or {}
    category_rows = []
    for candidate in pool.get("candidates") or []:
        sorftime = candidate.get("sorftime") or {}
        if sorftime.get("status") == "not_run":
            continue
        category_rows.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "theme": candidate.get("theme"),
                "status": sorftime.get("status"),
                "category_match": sorftime.get("category_match"),
                **(sorftime.get("data") or {}),
                "source_file": sorftime.get("response_file"),
            }
        )
    category_fields = ["candidate_id", "theme", "status", "category_match", "source_file"]
    write_csv(out / "06_sorftime_categories.csv", category_rows, fields_with_rows(category_fields, category_rows))

    product_files = sorftime_product_files(run)
    product_rows = load_sorftime_products(product_files, run)
    product_fields = ["rank", "asin", "title", "price", "star_rating", "review_count", "monthly_sales_volume", "main_image", "url", "semantic_relevance", "source_file", "online_date"]
    write_csv(out / "07_sorftime_products.csv", product_rows, fields_with_rows(product_fields, product_rows))

    amazon_files = sorted((run / "data" / "raw").glob("amazon_woot_*.jsonl"))
    amazon = load_jsonl(amazon_files[-1]) if amazon_files else []
    amazon_rows = [flatten_content(row) for row in amazon]
    write_csv(out / "08_amazon_reviews.csv", amazon_rows, fields_with_rows(content_fields, amazon_rows))

    evidence = load_json(run / "analysis" / "evidence_index.json", []) or []
    evidence_fields = ["candidate_id", "theme", "source_id", "platform", "content_type", "url", "text_raw", "pain_label"]
    write_csv(out / "09_evidence_index.csv", evidence, fields_with_rows(evidence_fields, evidence))

    calls = load_jsonl(run / "sorftime" / "call_log.jsonl")
    coverage = [
        {"source": "Google Trends", "count": len(trends_raw.get("series") or []), "unit": "keywords", "detail": f"{len(trend_rows)} weekly points", "file": "01_google_trends.csv"},
        {"source": "TikTok", "count": sum(1 for row in tiktok if row.get("content_type") == "video"), "unit": "videos", "detail": f"{sum(1 for row in tiktok if row.get('content_type') == 'comment')} comments", "file": "02_tiktok_videos.csv / 03_tiktok_comments.csv"},
        {"source": "Reddit", "count": sum(1 for row in reddit if (row.get("context") or {}).get("content_type") == "post"), "unit": "parent posts", "detail": f"{sum(1 for row in reddit if (row.get('context') or {}).get('content_type') == 'comment')} comments; modes: {', '.join(sorted({str((row.get('context') or {}).get('collection_mode') or 'unknown') for row in reddit})) or 'not_run'}", "file": "04_reddit_posts.csv / 05_reddit_comments.csv"},
        {"source": "Sorftime", "count": len(calls), "unit": "business calls", "detail": f"{len(product_rows)} product rows", "file": "06_sorftime_categories.csv / 07_sorftime_products.csv"},
        {"source": "Amazon", "count": len(amazon), "unit": "written reviews", "detail": f"{len({asin for row in amazon for asin in ((row.get('context') or {}).get('asins') or [])})} ASINs", "file": "08_amazon_reviews.csv"},
    ]
    write_csv(out / "00_data_coverage.csv", coverage, ["source", "count", "unit", "detail", "file"])
    print(json.dumps({"output_dir": str(out), "csv_files": len(list(out.glob("*.csv"))), "amazon_reviews": len(amazon)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
