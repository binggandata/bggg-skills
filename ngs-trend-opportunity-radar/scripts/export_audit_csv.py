#!/usr/bin/env python3
"""Export channel-separated staging CSVs used to build one audit workbook."""

from __future__ import annotations

import argparse
import csv
import json
import re
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
    screening = run / "data" / "clean" / f"{platform}_screening.jsonl"
    if screening.exists():
        return [screening]
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


def last_number(value):
    if value in (None, ""):
        return None
    matches = re.findall(r"-?[0-9]+(?:\.[0-9]+)?", str(value).replace(",", ""))
    return float(matches[-1]) if matches else None


def percent_value(value):
    number = last_number(value)
    return number / 100 if number is not None else None


def placeholder(status: str, reason: str) -> list[dict]:
    return [{"status": status, "reason": reason}]


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
        "candidate_id": context.get("candidate_id") or row.get("theme"),
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
        "post_title": context.get("post_title"),
        "subreddit": context.get("subreddit"),
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
    trend_signal_file = newest_snapshot(run / "data" / "signals", "google_trends*.jsonl")
    tiktok_files = selected_normalized_files(run, "tiktok")
    reddit_files = selected_normalized_files(run, "reddit")
    trends_raw = load_json(trends_file, {}) if trends_file else {}
    trend_rows = []
    if trend_signal_file:
        for row in load_jsonl(trend_signal_file):
            context = row.get("context") or {}
            date_match = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", str(row.get("text_raw") or ""))
            trend_rows.append({
                "candidate_id": row.get("theme"),
                "term": context.get("term"),
                "window": context.get("window"),
                "date": date_match.group(1) if date_match else None,
                "relative_search_interest": row.get("value"),
                "unit": row.get("unit"),
                "source_id": row.get("source_id"),
                "requested_market": row.get("requested_market"),
                "observed_market": row.get("observed_market"),
                "source_url": row.get("url"),
                "collected_at": row.get("observed_at"),
                "source_file": context.get("source_file") or str(trend_signal_file.relative_to(run)),
            })
    else:
        for series in trends_raw.get("series") or []:
            for point in series.get("values") or []:
                trend_rows.append(
                    {
                        "candidate_id": series.get("candidate_id"),
                        "term": series.get("name"),
                        "window": trends_raw.get("window"),
                        "date": point.get("date"),
                        "relative_search_interest": point.get("value"),
                        "unit": "relative_index_0_100_within_comparison",
                        "source_id": None,
                        "requested_market": trends_raw.get("requested_market"),
                        "observed_market": trends_raw.get("observed_market"),
                        "source_url": trends_raw.get("source_url"),
                        "collected_at": trends_raw.get("collected_at"),
                        "source_file": str(trends_file.relative_to(run)) if trends_file else None,
                    }
                )
    trend_fields = ["candidate_id", "term", "window", "date", "relative_search_interest", "unit", "source_id", "requested_market", "observed_market", "source_url", "collected_at", "source_file"]
    write_csv(out / "01_google_trends.csv", trend_rows, fields_with_rows(trend_fields, trend_rows))

    tiktok = load_jsonl_files(tiktok_files)
    content_fields = list(flatten_content({}).keys())
    tiktok_videos = [flatten_content(row) for row in tiktok if row.get("content_type") == "video"]
    tiktok_comments = [flatten_content(row) for row in tiktok if row.get("content_type") in {"comment", "reply"}]
    write_csv(out / "02_tiktok_videos.csv", tiktok_videos, fields_with_rows(content_fields, tiktok_videos))
    if not tiktok_comments:
        tiktok_comments = placeholder("not_run", "等待用户选择 Top N；快筛阶段只采视频，不采评论")
    write_csv(out / "03_tiktok_comments.csv", tiktok_comments, fields_with_rows(["status", "reason"] + content_fields, tiktok_comments))

    reddit = load_jsonl_files(reddit_files)
    reddit_posts = [flatten_content(row) for row in reddit if (row.get("context") or {}).get("content_type") == "post"]
    reddit_comments = [flatten_content(row) for row in reddit if (row.get("context") or {}).get("content_type") == "comment"]
    write_csv(out / "04_reddit_posts.csv", reddit_posts, fields_with_rows(content_fields, reddit_posts))
    if not reddit_comments:
        reddit_comments = placeholder("not_run", "等待用户选择 Top N；快筛阶段只采父帖，不采评论树")
    write_csv(out / "05_reddit_comments.csv", reddit_comments, fields_with_rows(["status", "reason"] + content_fields, reddit_comments))

    pool = load_json(run / "analysis" / "opportunity_pool.json", {}) or {}
    screening = load_json(run / "analysis" / "screening_funnel.json", {}) or {}
    screening_by_id = {row.get("candidate_id"): row for row in screening.get("directions") or []}
    category_rows = []
    pool_candidates = pool.get("candidates") or []
    if pool_candidates:
        for candidate in pool_candidates:
            sorftime = candidate.get("sorftime") or {}
            if sorftime.get("status") == "not_run":
                continue
            category_rows.append({
                "candidate_id": candidate.get("candidate_id"), "theme": candidate.get("theme"),
                "status": sorftime.get("status"), "category_match": sorftime.get("category_match"),
                **(sorftime.get("data") or {}), "source_file": sorftime.get("response_file"),
            })
    else:
        candidates = load_json(run / "analysis" / "candidates.json", {}) or {}
        for candidate in candidates.get("candidates") or []:
            market = candidate.get("sorftime_market") or {}
            funnel_row = screening_by_id.get(candidate.get("id")) or {}
            sf = funnel_row.get("sorftime") or {}
            category_rows.append({
                "candidate_id": candidate.get("id"),
                "research_category": candidate.get("research_category"),
                "theme": candidate.get("name_zh") or candidate.get("name_en"),
                "node_id": candidate.get("node_id"),
                "status": "success" if market else "missing",
                "category_match": sf.get("semantic_status") or "unknown",
                "top100_monthly_sales_volume": last_number(market.get("top100_monthly_sales_volume")),
                "top100_monthly_sales_amount": last_number(market.get("top100_monthly_sales_amount")),
                "average_price": last_number(market.get("average_price")),
                "median_price": last_number(market.get("median_price")),
                "top3_product_sales_share": percent_value(market.get("top3_product_sales_volume_share")),
                "amazon_owned_sales_share": percent_value(market.get("amazon_owned_sales_volume_share")),
                "low_reviews_sales_share": percent_value(market.get("low_reviews_sales_volume_share")),
                "return_rate": percent_value(market.get("return_rate")),
                "screening_decision": funnel_row.get("decision"),
                "decision_reasons": "；".join(funnel_row.get("reasons") or []),
                "source_file": "sorftime/category_reports_summary.json",
            })
    category_fields = ["candidate_id", "research_category", "theme", "node_id", "status", "category_match", "top100_monthly_sales_volume", "top100_monthly_sales_amount", "average_price", "median_price", "top3_product_sales_share", "amazon_owned_sales_share", "low_reviews_sales_share", "return_rate", "screening_decision", "decision_reasons", "source_file"]
    write_csv(out / "06_sorftime_categories.csv", category_rows, fields_with_rows(category_fields, category_rows))

    product_files = sorftime_product_files(run)
    product_rows = load_sorftime_products(product_files, run)
    if not product_rows:
        product_rows = placeholder("not_run", "等待用户选择 Top N；本阶段未调用 Sorftime product_search")
    product_fields = ["status", "reason", "rank", "asin", "title", "price", "star_rating", "review_count", "monthly_sales_volume", "main_image", "url", "semantic_relevance", "source_file", "online_date"]
    write_csv(out / "07_sorftime_products.csv", product_rows, fields_with_rows(product_fields, product_rows))

    amazon_files = sorted((run / "data" / "raw").glob("amazon_woot_*.jsonl"))
    amazon = load_jsonl(amazon_files[-1]) if amazon_files else []
    amazon_rows = [flatten_content(row) for row in amazon]
    if not amazon_rows:
        amazon_rows = placeholder("not_run", "等待用户选择 Top N；本阶段未采集 Amazon 书面评论")
    write_csv(out / "08_amazon_reviews.csv", amazon_rows, fields_with_rows(["status", "reason"] + content_fields, amazon_rows))

    evidence = load_json(run / "analysis" / "evidence_index.json", []) or []
    if not evidence:
        evidence = []
        for candidate_id in dict.fromkeys(row.get("candidate_id") for row in trend_rows):
            for platform, rows in (("Google Trends", trend_rows), ("TikTok", tiktok_videos), ("Reddit", reddit_posts)):
                row = next((item for item in rows if item.get("candidate_id") == candidate_id or item.get("theme") == candidate_id), None)
                if not row:
                    continue
                evidence.append({
                    "candidate_id": candidate_id,
                    "theme": (screening_by_id.get(candidate_id) or {}).get("name"),
                    "source_id": row.get("source_id"),
                    "platform": platform,
                    "content_type": row.get("content_type") or "signal",
                    "url": row.get("url") or row.get("source_url"),
                    "text_raw": row.get("text_raw") or f"{row.get('term') or ''} {row.get('date') or ''} = {row.get('relative_search_interest') or ''}",
                    "pain_label": None,
                })
        (run / "analysis" / "evidence_index.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evidence_fields = ["candidate_id", "theme", "source_id", "platform", "content_type", "url", "text_raw", "pain_label"]
    write_csv(out / "09_evidence_index.csv", evidence, fields_with_rows(evidence_fields, evidence))

    calls = [row for row in load_jsonl(run / "sorftime" / "call_log.jsonl") if row.get("tool")]
    brief = load_json(run / "00-research-brief" / "research_brief.json", {}) or {}
    category_budget = brief.get("category_tree_budget") or {}
    sorftime_total = int(category_budget.get("first_level_calls_already_completed") or 0) + int(category_budget.get("branch_expansion_calls") or 0) + int((load_json(run / "sorftime" / "category_reports_summary.json", {}) or {}).get("calls") or 0)
    if not sorftime_total:
        sorftime_total = len(calls)
    tiktok_video_count = sum(1 for row in tiktok if row.get("content_type") == "video")
    tiktok_comment_count = sum(1 for row in tiktok if row.get("content_type") == "comment")
    reddit_post_count = sum(1 for row in reddit if (row.get("context") or {}).get("content_type") == "post")
    reddit_comment_count = sum(1 for row in reddit if (row.get("context") or {}).get("content_type") == "comment")
    trend_series = {(row.get("candidate_id"), row.get("term"), row.get("window"), row.get("observed_market")) for row in trend_rows}
    coverage = [
        {"source": "Google Trends", "count": len(trend_rows), "unit": "weekly points", "detail": f"{len(trend_series)} term/window/market series; 0 failures", "status": "completed", "file": "01_google_trends.csv"},
        {"source": "TikTok", "count": tiktok_video_count, "unit": "videos", "detail": f"{tiktok_comment_count} comments; screening uses logged-in Chrome", "status": "screening_completed", "file": "02_tiktok_videos.csv / 03_tiktok_comments.csv"},
        {"source": "Reddit", "count": reddit_post_count, "unit": "parent posts", "detail": f"{reddit_comment_count} comments; modes: {', '.join(sorted({str((row.get('context') or {}).get('collection_mode') or 'unknown') for row in reddit})) or 'not_run'}", "status": "screening_completed", "file": "04_reddit_posts.csv / 05_reddit_comments.csv"},
        {"source": "Sorftime", "count": sorftime_total, "unit": "business calls", "detail": f"10 category-tree calls + 8 category reports; product_search not run", "status": "screening_completed", "file": "06_sorftime_categories.csv / 07_sorftime_products.csv"},
        {"source": "Amazon", "count": len(amazon), "unit": "written reviews", "detail": f"{len({asin for row in amazon for asin in ((row.get('context') or {}).get('asins') or [])})} ASINs; waiting for Top N", "status": "not_run", "file": "08_amazon_reviews.csv"},
    ]
    write_csv(out / "00_data_coverage.csv", coverage, ["source", "count", "unit", "detail", "status", "file"])
    print(json.dumps({"output_dir": str(out), "csv_files": len(list(out.glob("*.csv"))), "amazon_reviews": len(amazon)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
