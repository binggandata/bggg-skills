#!/usr/bin/env python3
"""Assign transparent A/B/C/D grades without an uncalibrated numeric score."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}
PLATFORM_NAMES = {
    "amazon": "Amazon",
    "google trends": "Google Trends",
    "reddit": "Reddit",
    "sorftime": "Sorftime",
    "tiktok": "TikTok",
}


def canonical_platform(value: object) -> str:
    return PLATFORM_NAMES.get(str(value or "").strip().casefold(), "")


def source_cluster(row: dict) -> str:
    context = row.get("context") or {}
    platform = canonical_platform(row.get("platform"))
    asins = context.get("asins") or []
    if platform == "Amazon":
        parent = (
            row.get("parent_source_id")
            or context.get("asin")
            or row.get("asin")
            or (asins[0] if isinstance(asins, list) and asins else "")
        )
        return f"Amazon:{str(parent).strip().upper()}" if parent else ""
    parent = str(
        row.get("parent_source_id")
        or row.get("parent_video_id")
        or context.get("parent_video_id")
        or context.get("post_id")
        or context.get("asin")
        or row.get("asin")
        or ""
    )
    if parent:
        return f"{platform}:{parent}"
    content_type = str(row.get("content_type") or context.get("content_type") or "").strip().casefold()
    if content_type in {"post", "video"} and row.get("source_id"):
        return f"{platform}:{row['source_id']}"
    return ""


def distinct_platforms(rows: list[dict]) -> set[str]:
    return {name for row in rows if (name := canonical_platform(row.get("platform")))}


def trend_row_usable(row: dict) -> bool:
    status = str(row.get("query_semantic_status") or row.get("semantic_status") or "not_checked").lower()
    return status in {"matched", "relevant"} and all(row.get(key) for key in ("source_id", "url", "observed_at"))


def pain_row_usable(row: dict) -> bool:
    context = row.get("context") or {}
    return bool(row.get("platform") and row.get("source_id") and row.get("text_raw") and (row.get("url") or context.get("url") or context.get("video_url")))


def amazon_market_usable(row: dict, requested_market: str) -> bool:
    context = row.get("context") or {}
    observed = str(row.get("observed_market") or context.get("observed_market") or "").upper()
    requested = requested_market.upper()
    us_aliases = {"US", "USA", "UNITED STATES", "美国"}
    if requested in us_aliases:
        return not observed or observed in us_aliases
    return bool(observed and observed == requested)


def sorftime_usable(sorftime: dict) -> bool:
    status = str(sorftime.get("status") or "not_run").lower()
    category_match = str(sorftime.get("category_match") or "not_checked").lower()
    return status in {"validated", "partial"} and category_match in {"exact", "relevant"}


def grade_candidate(candidate: dict) -> dict:
    all_trend = list(candidate.get("trend_evidence") or candidate.get("evidence") or [])
    all_pain = list(candidate.get("pain_evidence") or [])
    reddit_gate_status = str(candidate.get("reddit_sample_gate_status") or "not_checked").lower()
    reddit_gate_detail = candidate.get("reddit_sample_gate_detail") or {}
    reddit_parent_posts = int(reddit_gate_detail.get("parent_posts") or 0)
    reddit_comment_parent_posts = int(reddit_gate_detail.get("comment_parent_posts") or 0)
    reddit_relevant_posts = int(reddit_gate_detail.get("relevant_posts") or 0)
    reddit_comment_rows = int(reddit_gate_detail.get("comment_rows") or 0)
    reddit_quick_gate_passed = (
        reddit_gate_status in {"quick_passed", "passed", "deep_passed"}
        and reddit_relevant_posts >= 10
        and reddit_parent_posts >= 10
    )
    reddit_deep_gate_passed = (
        reddit_gate_status in {"passed", "deep_passed"}
        and reddit_relevant_posts >= 10
        and reddit_comment_parent_posts >= 5
        and reddit_comment_rows >= 100
    )
    trend = [
        row for row in all_trend
        if trend_row_usable(row)
        and (canonical_platform(row.get("platform")) != "Reddit" or reddit_quick_gate_passed)
    ]
    pain = [
        row for row in all_pain
        if pain_row_usable(row)
        and canonical_platform(row.get("platform"))
        and (canonical_platform(row.get("platform")) != "Reddit" or reddit_deep_gate_passed)
    ]
    trend_platforms = distinct_platforms(trend)
    pain_clusters = {source_cluster(row) for row in pain if source_cluster(row)}
    requested_market = str(candidate.get("requested_market") or "")
    amazon_pain_all = [row for row in pain if canonical_platform(row.get("platform")) == "Amazon"]
    amazon_pain = [row for row in amazon_pain_all if amazon_market_usable(row, requested_market)]
    sorftime = candidate.get("sorftime") or {}
    sorftime_status = str(sorftime.get("status") or "not_run")
    category_match = str(sorftime.get("category_match") or "not_checked")
    commercial_usable = sorftime_usable(sorftime)
    hard = list(candidate.get("hard_exclusions") or [])
    critical_missing = list(candidate.get("critical_missing") or [])
    refuted = bool(candidate.get("refuted"))
    constraints_fit = candidate.get("constraints_fit")
    sample_gate_status = str(candidate.get("sample_gate_status") or "not_checked").lower()
    sample_gate_detail = candidate.get("sample_gate_detail") or {}
    tiktok_relevant_videos = int(sample_gate_detail.get("relevant_videos") or 0)
    tiktok_accounts = int(sample_gate_detail.get("accounts") or 0)
    tiktok_comment_parent_videos = int(sample_gate_detail.get("comment_parent_videos") or 0)
    tiktok_comment_rows = int(sample_gate_detail.get("comment_rows") or 0)
    tiktok_quick_gate_passed = (
        sample_gate_status in {"quick_passed", "passed", "deep_passed"}
        and tiktok_relevant_videos >= 10
        and tiktok_accounts >= 5
    )
    sample_gate_passed = (
        sample_gate_status in {"passed", "deep_passed"}
        and tiktok_relevant_videos >= 20
        and tiktok_comment_parent_videos >= 5
        and tiktok_comment_rows >= 100
    )

    reasons: list[str] = []
    missing: list[str] = list(critical_missing)
    if hard:
        reasons.append("命中硬排除：" + "；".join(map(str, hard)))
    if refuted:
        reasons.append("趋势或痛点已被反证")
    if constraints_fit is False:
        reasons.append("与用户约束明显冲突")

    if hard or refuted or constraints_fit is False:
        grade = "D"
    elif len(trend_platforms) >= 2 and len(pain_clusters) >= 2 and amazon_pain and sorftime_status == "validated" and commercial_usable and sample_gate_passed and not critical_missing:
        grade = "A"
        reasons.append("跨平台趋势、独立痛点簇与商业验证均通过")
    elif len(trend_platforms) >= 2 and len(pain_clusters) >= 1 and commercial_usable:
        grade = "B"
        reasons.append("方向成立，但仍有关键缺口或风险待验证")
    else:
        grade = "C"
        reasons.append("存在信号，但交叉、痛点或商业证据不足")

    if len(trend_platforms) < 2:
        missing.append("至少两个独立趋势平台")
    if len(pain_clusters) < 1:
        missing.append("真实痛点证据")
    elif len(pain_clusters) < 2:
        missing.append("第二个独立父级痛点证据簇")
    rejected_trend = sum(not trend_row_usable(row) for row in all_trend)
    if rejected_trend:
        missing.append("趋势查询语义复核")
    if not commercial_usable:
        if category_match.lower() in {"ambiguous", "mismatch"}:
            missing.append("Sorftime 相关类目商业验证")
        else:
            missing.append("Sorftime 商业验证")
    if not amazon_pain:
        missing.append("目标市场可用的 Amazon 买后评论验证")
    if not sample_gate_passed:
        missing.append("TikTok 深验样本门槛")
    if any(canonical_platform(row.get("platform")) == "Reddit" for row in all_trend) and not reddit_quick_gate_passed:
        missing.append("Reddit 快筛样本门槛")
    if any(canonical_platform(row.get("platform")) == "Reddit" for row in all_pain) and not reddit_deep_gate_passed:
        missing.append("Reddit 独立父帖深验门槛")

    result = dict(candidate)
    result.update(
        {
            "grade": grade,
            "grade_reasons": reasons,
            "missing_evidence": sorted(dict.fromkeys(missing)),
            "metrics": {
                "trend_platform_count": len(trend_platforms),
                "trend_platforms": sorted(trend_platforms),
                "trend_semantic_rejected_count": rejected_trend,
                "pain_evidence_count": len(pain),
                "pain_parent_cluster_count": len(pain_clusters),
                "amazon_pain_evidence_count": len(amazon_pain),
                "amazon_pain_out_of_market_count": len(amazon_pain_all) - len(amazon_pain),
                "sample_gate_status": sample_gate_status,
                "sample_gate_passed": sample_gate_passed,
                "tiktok_relevant_videos": tiktok_relevant_videos,
                "tiktok_accounts": tiktok_accounts,
                "tiktok_comment_parent_videos": tiktok_comment_parent_videos,
                "tiktok_comment_rows": tiktok_comment_rows,
                "tiktok_quick_gate_passed": tiktok_quick_gate_passed,
                "reddit_sample_gate_status": reddit_gate_status,
                "reddit_parent_posts": reddit_parent_posts,
                "reddit_comment_parent_posts": reddit_comment_parent_posts,
                "reddit_relevant_posts": reddit_relevant_posts,
                "reddit_comment_rows": reddit_comment_rows,
                "reddit_quick_gate_passed": reddit_quick_gate_passed,
                "reddit_deep_gate_passed": reddit_deep_gate_passed,
                "sorftime_status": sorftime_status,
                "sorftime_category_match": category_match,
                "sorftime_usable": commercial_usable,
            },
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    candidates = payload.get("candidates") or payload.get("themes") or payload
    if not isinstance(candidates, list):
        raise SystemExit("Input must be a list or contain candidates/themes list.")
    graded = [grade_candidate(candidate) for candidate in candidates]
    graded.sort(
        key=lambda row: (
            GRADE_ORDER[row["grade"]],
            int(row.get("priority_order") or 999),
            -row["metrics"]["trend_platform_count"],
            -row["metrics"]["pain_parent_cluster_count"],
            str(row.get("theme") or row.get("candidate_id") or ""),
        )
    )
    counts = {grade: sum(1 for row in graded if row["grade"] == grade) for grade in "ABCD"}
    output_payload = {"candidates": graded, "summary": {"total": len(graded), "by_grade": counts}}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output_payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
