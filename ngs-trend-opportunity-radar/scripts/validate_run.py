#!/usr/bin/env python3
"""Validate report artifacts, evidence invariants, and Sorftime call budget."""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


DEFAULT_TOOLS = {"category_search_from_product_name", "category_trend", "product_search"}
DEFAULT_BLOCKED = {"product_detail", "product_reviews", "category_report"}
WORKBOOK_SHEETS = [
    ("00_data_coverage.csv", "00 数据覆盖"),
    ("01_google_trends.csv", "01 Google Trends"),
    ("02_tiktok_videos.csv", "02 TikTok视频"),
    ("03_tiktok_comments.csv", "03 TikTok评论"),
    ("04_reddit_posts.csv", "04 Reddit帖子"),
    ("05_reddit_comments.csv", "05 Reddit评论"),
    ("06_sorftime_categories.csv", "06 Sorftime品类"),
    ("07_sorftime_products.csv", "07 Sorftime商品"),
    ("08_amazon_reviews.csv", "08 Amazon评论"),
    ("09_evidence_index.csv", "09 证据索引"),
]
REPORT_SECTION_IDS = [
    "executive-summary", "research-scope", "decision-summary", "data-coverage", "trend-evidence",
    "social-evidence", "commercial-evidence", "voc-pains", "product-opportunity", "decision-risks",
    "candidate-pool", "evidence-trace", "data-download", "follow-up-consultation",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def csv_row_count(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def dedupe_reddit_rows(paths: list[Path]) -> dict[str, dict]:
    unique: dict[str, dict] = {}
    for source_file in paths:
        for row in load_jsonl(source_file):
            key = str(row.get("native_id") or row.get("source_id") or "")
            if not key:
                continue
            existing = unique.get(key)
            existing_mode = str(((existing or {}).get("context") or {}).get("collection_mode") or "")
            current_mode = str((row.get("context") or {}).get("collection_mode") or "")
            if not existing or (existing_mode == "visible_dom" and current_mode != "visible_dom"):
                unique[key] = row
    return unique


def selected_reddit_files(run_dir: Path) -> list[Path]:
    raw = run_dir / "data" / "raw"
    visible = list(raw.glob("reddit_visible_*.jsonl"))
    candidates = visible or list(raw.glob("reddit*.jsonl"))
    return [max(candidates, key=lambda path: path.stat().st_mtime_ns)] if candidates else []


def candidate_needs_tiktok_gate(candidate: dict) -> bool:
    return candidate.get("grade") in {"A", "B"} or int(candidate.get("priority_order") or 999) == 1


def call_arguments(call: dict) -> dict:
    for key in ("arguments_redacted", "arguments", "input", "params"):
        if isinstance(call.get(key), dict):
            return call[key]
    return {}


def tool_name(call: dict) -> str:
    return str(call.get("tool") or "").strip().rsplit("/", 1)[-1].rsplit(".", 1)[-1]


def inspect_xlsx(path: Path) -> dict[str, int]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    rel_ns = {"p": "http://schemas.openxmlformats.org/package/2006/relationships"}
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {row.attrib["Id"]: row.attrib["Target"] for row in rels.findall("p:Relationship", rel_ns)}
        result = {}
        for sheet in workbook.findall("m:sheets/m:sheet", ns):
            target = targets[sheet.attrib[f"{{{ns['r']}}}id"]].lstrip("/")
            sheet_path = target if target.startswith("xl/") else f"xl/{target}"
            root = ET.fromstring(archive.read(sheet_path))
            row_numbers = [int(row.attrib.get("r", 0)) for row in root.findall("m:sheetData/m:row", ns)]
            result[sheet.attrib["name"]] = max(0, max(row_numbers, default=4) - 4)
        return result


def validate(run_dir: Path, soft_cap: int, hard_cap: int) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    consistency: dict[str, object] = {}
    required = [
        run_dir / "00-research-brief" / "research_brief.json",
        run_dir / "analysis" / "opportunity_pool.json",
        run_dir / "analysis" / "evidence_index.json",
        run_dir / "analysis" / "amazon_pain_stats.json",
        run_dir / "report" / "report.md",
        run_dir / "report" / "report.html",
        run_dir / "report" / "research_data.xlsx",
    ]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"missing_or_empty:{path.relative_to(run_dir)}")

    brief_path = run_dir / "00-research-brief" / "research_brief.json"
    if brief_path.exists():
        brief = load_json(brief_path)
        business_fields = ["requested_market", "target_sales_platform", "broad_category", "output_location"]
        missing_business_fields = [field for field in business_fields if not brief.get(field)]
        consistency["business_card_fields"] = {field: brief.get(field) for field in business_fields}
        if missing_business_fields:
            errors.append(f"missing_business_card_fields:{','.join(missing_business_fields)}")
        login_candidates = list(brief.get("login_session_candidates") or [])
        login_selection = brief.get("login_session_selection") or {}
        consistency["login_session_candidates"] = len(login_candidates)
        consistency["login_session_selection_mode"] = login_selection.get("mode")
        if len(login_candidates) > 1:
            mode = login_selection.get("mode")
            valid_single = mode == "single" and bool(login_selection.get("session_id"))
            mapping = login_selection.get("mapping") or {}
            valid_mapping = mode == "per_source" and all(mapping.get(source) for source in ("google_trends", "tiktok"))
            if not (valid_single or valid_mapping):
                errors.append("multiple_login_sessions_require_user_selection")
        serialized_brief = json.dumps(brief, ensure_ascii=False).lower()
        if any(marker in serialized_brief for marker in ("cookie", "access_token", "refresh_token", "password")):
            errors.append("possible_secret_in_research_brief")

    pool_path = run_dir / "analysis" / "opportunity_pool.json"
    if pool_path.exists():
        for candidate in load_json(pool_path).get("candidates", []):
            grade = candidate.get("grade")
            metrics = candidate.get("metrics") or {}
            if grade in {"A", "B"} and metrics.get("trend_platform_count", 0) < 2:
                errors.append(f"{candidate.get('candidate_id')}:grade_{grade}_needs_two_trend_platforms")
            if grade == "A" and metrics.get("pain_parent_cluster_count", 0) < 2:
                errors.append(f"{candidate.get('candidate_id')}:grade_A_needs_two_pain_clusters")
            if grade == "A" and (metrics.get("sorftime_status") != "validated" or not metrics.get("sorftime_usable")):
                errors.append(f"{candidate.get('candidate_id')}:grade_A_needs_validated_sorftime")
            if grade == "A" and metrics.get("amazon_pain_evidence_count", 0) < 1:
                errors.append(f"{candidate.get('candidate_id')}:grade_A_needs_amazon_reviews")
            if grade == "A" and not metrics.get("sample_gate_passed"):
                errors.append(f"{candidate.get('candidate_id')}:grade_A_needs_deep_sample_gate")
            if grade == "A" and metrics.get("amazon_pain_out_of_market_count", 0):
                errors.append(f"{candidate.get('candidate_id')}:grade_A_contains_out_of_market_amazon_reviews")
            if grade in {"A", "B"} and metrics.get("trend_semantic_rejected_count", 0):
                errors.append(f"{candidate.get('candidate_id')}:grade_{grade}_contains_semantic_mismatch")

    calls = load_jsonl(run_dir / "sorftime" / "call_log.jsonl")
    if len(calls) > hard_cap:
        approved_caps = [int(row.get("approved_call_cap") or 0) for row in calls if row.get("user_approved")]
        approved_cap = max(approved_caps, default=hard_cap)
        if len(calls) > approved_cap:
            errors.append(f"sorftime_calls:{len(calls)}>approved_cap:{approved_cap}")
        else:
            warnings.append(f"sorftime_calls:{len(calls)}>default_hard_cap:{hard_cap}:user_approved")
    elif len(calls) > soft_cap:
        missing_reasons = [idx + 1 for idx, row in enumerate(calls[soft_cap:]) if not row.get("reason")]
        if missing_reasons:
            errors.append("sorftime_calls_over_soft_cap_without_reason")
        else:
            warnings.append(f"sorftime_calls:{len(calls)}>soft_cap:{soft_cap}")
    for idx, call in enumerate(calls, 1):
        tool = tool_name(call)
        arguments = call_arguments(call)
        try:
            page = int(arguments.get("page") or call.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        if tool in DEFAULT_BLOCKED and not call.get("user_approved"):
            errors.append(f"call_{idx}:{tool}:requires_user_approval")
        if tool not in DEFAULT_TOOLS and not call.get("user_approved"):
            warnings.append(f"call_{idx}:non_default_tool:{tool}")
        if tool == "product_search" and page in {2, 3}:
            if call.get("reason") != "semantic_pagination":
                errors.append(f"call_{idx}:product_search:page_{page}_needs_semantic_pagination_reason")
            if call.get("new_valid_asins") is None and call.get("new_valid_count") is None:
                errors.append(f"call_{idx}:product_search:page_{page}_needs_new_valid_asin_count")
        if tool == "product_search" and page >= 4:
            if not call.get("user_approved"):
                errors.append(f"call_{idx}:product_search:page_{page}_requires_user_approval")
            elif int(call.get("approved_max_page") or 0) < page:
                errors.append(f"call_{idx}:product_search:page_{page}_exceeds_approved_max_page")
        serialized = json.dumps(call, ensure_ascii=False).lower()
        if any(marker in serialized for marker in ("mcp_key", "account-sk", "cookie", "access_token")):
            errors.append(f"call_{idx}:possible_secret_in_log")

    html_path = run_dir / "report" / "report.html"
    if html_path.exists():
        html_text = html_path.read_text(encoding="utf-8")
        section_positions = [html_text.find(f'id="{section_id}"') for section_id in REPORT_SECTION_IDS]
        missing_sections = [section_id for section_id, position in zip(REPORT_SECTION_IDS, section_positions) if position < 0]
        if missing_sections:
            errors.append("report_template_missing_sections:" + ",".join(missing_sections))
        elif section_positions != sorted(section_positions):
            errors.append("report_template_section_order_mismatch")
        if html_text.count('class="viz"') < 4:
            errors.append("report_needs_at_least_four_visual_charts")
        if 'href="research_data.xlsx"' not in html_text:
            errors.append("report_needs_single_workbook_download")
        if 'href="data/' in html_text:
            errors.append("report_must_not_expose_individual_csv_downloads")
        if 'class="consult"' not in html_text:
            errors.append("report_needs_follow_up_consultation_section")
        pool = load_json(pool_path) if pool_path.exists() else {}
        candidates = pool.get("candidates") or []
        top = candidates[0] if candidates else {}
        representative_asins = (((top.get("sorftime") or {}).get("product_search") or {}).get("representative_asins") or [])
        product_cards = html_text.count('class="product-card"')
        consistency["representative_asins"] = len(representative_asins)
        consistency["product_cards"] = product_cards
        if representative_asins and product_cards < len(representative_asins):
            errors.append(f"product_cards:{product_cards}<representative_asins:{len(representative_asins)}")
        if representative_asins and 'text-anchor="end" class="bar-value"' not in html_text:
            errors.append("bar_chart_labels_need_right_edge_protection")
        if product_cards and 'class="product-image-missing"' not in html_text and 'src="data:image/' not in html_text:
            errors.append("product_cards_need_embedded_image_or_explicit_placeholder")

        evidence_path = run_dir / "analysis" / "evidence_index.json"
        evidence_rows_for_html = load_json(evidence_path) if evidence_path.exists() else []
        if any(len(str(row.get("text_raw") or "")) > 140 for row in evidence_rows_for_html) and 'class="quote-details"' not in html_text:
            errors.append("long_evidence_needs_expandable_full_text")

    amazon_files = sorted((run_dir / "data" / "raw").glob("amazon_woot_*.jsonl"))
    staging_dir = run_dir / "work" / "workbook-sources"
    amazon_csv = staging_dir / "08_amazon_reviews.csv"
    if amazon_files and amazon_csv.exists():
        amazon_jsonl_rows = len(load_jsonl(amazon_files[-1]))
        amazon_csv_rows = csv_row_count(amazon_csv)
        consistency["amazon_jsonl_rows"] = amazon_jsonl_rows
        consistency["amazon_csv_rows"] = amazon_csv_rows
        if amazon_jsonl_rows != amazon_csv_rows:
            errors.append(f"amazon_csv_rows:{amazon_csv_rows}!=jsonl_rows:{amazon_jsonl_rows}")

    reddit_files = selected_reddit_files(run_dir)
    reddit_rows = dedupe_reddit_rows(reddit_files)
    reddit_post_count = sum((row.get("context") or {}).get("content_type") == "post" for row in reddit_rows.values())
    reddit_comment_count = sum((row.get("context") or {}).get("content_type") == "comment" for row in reddit_rows.values())
    consistency["reddit_jsonl_unique_posts"] = reddit_post_count
    consistency["reddit_jsonl_unique_comments"] = reddit_comment_count
    for csv_name, expected in (("04_reddit_posts.csv", reddit_post_count), ("05_reddit_comments.csv", reddit_comment_count)):
        csv_path = staging_dir / csv_name
        if csv_path.exists() and csv_row_count(csv_path) != expected:
            errors.append(f"reddit_csv_rows:{csv_name}:{csv_row_count(csv_path)}!=jsonl_rows:{expected}")

    reddit_gates_path = run_dir / "analysis" / "reddit_sample_gates.json"
    reddit_gates = load_json(reddit_gates_path).get("themes", {}) if reddit_gates_path.exists() else {}
    if pool_path.exists():
        for candidate in load_json(pool_path).get("candidates", []):
            metrics = candidate.get("metrics") or {}
            all_reddit_evidence = [
                row for row in list(candidate.get("trend_evidence") or []) + list(candidate.get("pain_evidence") or [])
                if str(row.get("platform") or "").lower() == "reddit"
            ]
            if not all_reddit_evidence:
                continue
            theme_key = str(candidate.get("reddit_theme_key") or candidate.get("theme") or "")
            actual = reddit_gates.get(theme_key)
            if not actual:
                errors.append(f"{candidate.get('candidate_id')}:missing_reddit_sample_gate_analysis")
                continue
            expected_fields = {
                "reddit_relevant_posts": actual.get("relevant_posts"),
                "reddit_parent_posts": actual.get("parent_posts"),
                "reddit_comment_parent_posts": actual.get("comment_parent_posts"),
                "reddit_comment_rows": actual.get("comment_rows"),
                "reddit_quick_gate_passed": actual.get("quick_gate_passed"),
                "reddit_deep_gate_passed": actual.get("deep_gate_passed"),
            }
            for field, expected in expected_fields.items():
                if metrics.get(field) != expected:
                    errors.append(f"{candidate.get('candidate_id')}:{field}:{metrics.get(field)}!=reddit_analysis:{expected}")
            if "Reddit" in (metrics.get("trend_platforms") or []) and not actual.get("quick_gate_passed"):
                errors.append(f"{candidate.get('candidate_id')}:reddit_trend_needs_quick_gate")

    tiktok_gates_path = run_dir / "analysis" / "tiktok_sample_gates.json"
    tiktok_gates = load_json(tiktok_gates_path).get("themes", {}) if tiktok_gates_path.exists() else {}
    if pool_path.exists():
        for candidate in load_json(pool_path).get("candidates", []):
            metrics = candidate.get("metrics") or {}
            has_tiktok = any(
                str(row.get("platform") or "").strip().casefold() == "tiktok"
                for row in list(candidate.get("trend_evidence") or []) + list(candidate.get("pain_evidence") or [])
            )
            if not has_tiktok:
                continue
            if not candidate_needs_tiktok_gate(candidate):
                continue
            theme_key = str(candidate.get("tiktok_theme_key") or candidate.get("theme") or "")
            actual = tiktok_gates.get(theme_key)
            if not actual:
                errors.append(f"{candidate.get('candidate_id')}:missing_tiktok_sample_gate_analysis")
                continue
            expected_fields = {
                "tiktok_relevant_videos": actual.get("relevant_videos"),
                "tiktok_accounts": actual.get("accounts"),
                "tiktok_comment_parent_videos": actual.get("comment_parent_videos"),
                "tiktok_comment_rows": actual.get("comment_rows"),
                "tiktok_quick_gate_passed": actual.get("quick_gate_passed"),
                "sample_gate_passed": actual.get("deep_gate_passed"),
            }
            for field, expected in expected_fields.items():
                if metrics.get(field) != expected:
                    errors.append(f"{candidate.get('candidate_id')}:{field}:{metrics.get(field)}!=tiktok_analysis:{expected}")
            if candidate.get("grade") == "A" and not actual.get("deep_gate_passed"):
                errors.append(f"{candidate.get('candidate_id')}:grade_A_needs_tiktok_deep_gate")

    workbook_path = run_dir / "report" / "research_data.xlsx"
    if workbook_path.exists():
        try:
            workbook_rows = inspect_xlsx(workbook_path)
            expected_names = [name for _, name in WORKBOOK_SHEETS]
            consistency["workbook_sheets"] = workbook_rows
            if list(workbook_rows) != expected_names:
                errors.append("workbook_sheet_names_or_order_mismatch")
            for csv_name, sheet_name in WORKBOOK_SHEETS:
                csv_path = staging_dir / csv_name
                if not csv_path.exists():
                    errors.append(f"missing_workbook_source:{csv_name}")
                    continue
                csv_rows = csv_row_count(csv_path)
                if workbook_rows.get(sheet_name) != csv_rows:
                    errors.append(f"workbook_rows:{sheet_name}:{workbook_rows.get(sheet_name)}!=csv_rows:{csv_rows}")
        except (KeyError, OSError, ET.ParseError, zipfile.BadZipFile) as exc:
            errors.append(f"invalid_research_workbook:{type(exc).__name__}")

    evidence_path = run_dir / "analysis" / "evidence_index.json"
    if evidence_path.exists():
        known_ids = set()
        for pattern in ("data/raw/*.jsonl", "data/signals/*.jsonl"):
            for source_file in run_dir.glob(pattern):
                known_ids.update(str(row.get("source_id")) for row in load_jsonl(source_file) if row.get("source_id"))
        evidence_rows = load_json(evidence_path)
        unresolved = sorted({str(row.get("source_id")) for row in evidence_rows if row.get("source_id") and str(row.get("source_id")) not in known_ids})
        consistency["evidence_rows"] = len(evidence_rows)
        consistency["unresolved_source_ids"] = unresolved
        if unresolved and known_ids:
            errors.append(f"unresolved_source_ids:{len(unresolved)}")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "sorftime_calls": len(calls),
        "soft_call_cap": soft_cap,
        "hard_call_cap": hard_cap,
        "consistency": consistency,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--soft-call-cap", type=int, default=2)
    parser.add_argument("--hard-call-cap", type=int, default=5)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    result = validate(run_dir, args.soft_call_cap, args.hard_call_cap)
    quality = run_dir / "quality"
    quality.mkdir(parents=True, exist_ok=True)
    (quality / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
