#!/usr/bin/env python3

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


rank = load_module("rank_candidates", "rank_candidates.py")
render = load_module("render_report", "render_report.py")
validate = load_module("validate_run", "validate_run.py")
tiktok = load_module("bggg_data_tiktok", "bggg_data_tiktok.py")
tiktok_plan = load_module("bggg_data_tiktok_plan", "bggg_data_tiktok_plan.py")
tiktok_normalize = load_module("bggg_data_tiktok_normalize", "bggg_data_tiktok_normalize.py")
tiktok_analyze = load_module("analyze_tiktok_samples", "analyze_tiktok_samples.py")
reddit_analyze = load_module("analyze_reddit_samples", "analyze_reddit_samples.py")
reddit_api = load_module("bggg_data_reddit_api", "bggg_data_reddit_api.py")
reddit_normalize = load_module("bggg_data_reddit_normalize", "bggg_data_reddit_normalize.py")
sys.modules["bggg_data_reddit_normalize"] = reddit_normalize
reddit_visible_normalize = load_module("bggg_data_reddit_visible_normalize", "bggg_data_reddit_visible_normalize.py")
export = load_module("export_audit_csv", "export_audit_csv.py")


class MainScriptsTest(unittest.TestCase):
    def write_minimal_workbook(self, path, sheets):
        workbook_sheets = "".join(f'<sheet name="{name}" sheetId="{idx}" r:id="rId{idx}"/>' for idx, name in enumerate(sheets, 1))
        rels = "".join(f'<Relationship Id="rId{idx}" Type="worksheet" Target="worksheets/sheet{idx}.xml"/>' for idx in range(1, len(sheets) + 1))
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("xl/workbook.xml", f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{workbook_sheets}</sheets></workbook>')
            archive.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
            for idx in range(1, len(sheets) + 1):
                archive.writestr(f"xl/worksheets/sheet{idx}.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="4"><c r="A4"/></row></sheetData></worksheet>')

    def candidate(self):
        return {
            "candidate_id": "theme-1",
            "theme": "Drawer organizer",
            "platforms": ["TikTok", "Google Trends"],
            "trend_evidence": [
                {"platform": "TikTok", "source_id": "t1", "url": "https://example.com/t1", "observed_at": "2026-08-24T00:00:00Z", "query_semantic_status": "matched"},
                {"platform": "Google Trends", "source_id": "g1", "url": "https://example.com/g1", "observed_at": "2026-08-24T00:00:00Z", "query_semantic_status": "matched"},
            ],
            "pain_evidence": [
                {"platform": "Amazon", "source_id": "a1", "url": "https://example.com/a1", "parent_source_id": "asin-1", "text_raw": "dividers slip"},
                {"platform": "Amazon", "source_id": "a2", "url": "https://example.com/a2", "parent_source_id": "asin-2", "text_raw": "arrived cracked"},
            ],
            "sorftime": {"status": "validated", "category_match": "exact"},
            "hard_exclusions": [],
            "critical_missing": [],
            "constraints_fit": True,
            "requested_market": "US",
            "sample_gate_status": "passed",
            "sample_gate_detail": {"relevant_videos": 20, "accounts": 5, "comment_parent_videos": 5, "comment_rows": 100},
        }

    def test_grade_a(self):
        graded = rank.grade_candidate(self.candidate())
        self.assertEqual(graded["grade"], "A")
        self.assertEqual(graded["metrics"]["pain_parent_cluster_count"], 2)

    def test_platform_names_are_normalized_and_amazon_pains_cluster_by_asin(self):
        candidate = self.candidate()
        candidate["trend_evidence"][0]["platform"] = " tiktok "
        candidate["trend_evidence"][1]["platform"] = "TIKTOK"
        candidate["pain_evidence"] = [
            {"platform": " amazon ", "source_id": "a1", "url": "https://example.com/review/1", "text_raw": "slips", "context": {"asins": ["B000SAME"]}},
            {"platform": "AMAZON", "source_id": "a2", "url": "https://example.com/review/2", "text_raw": "cracks", "context": {"asins": ["B000SAME"]}},
        ]
        graded = rank.grade_candidate(candidate)
        self.assertEqual(graded["metrics"]["trend_platform_count"], 1)
        self.assertEqual(graded["metrics"]["trend_platforms"], ["TikTok"])
        self.assertEqual(graded["metrics"]["pain_parent_cluster_count"], 1)

    def test_hard_exclusion_is_d(self):
        candidate = self.candidate()
        candidate["hard_exclusions"] = ["excluded category"]
        self.assertEqual(rank.grade_candidate(candidate)["grade"], "D")

    def test_semantic_or_category_mismatch_cannot_upgrade(self):
        candidate = self.candidate()
        candidate["trend_evidence"][0]["query_semantic_status"] = "mismatch"
        candidate["sorftime"] = {"status": "partial", "category_match": "mismatch"}
        graded = rank.grade_candidate(candidate)
        self.assertEqual(graded["grade"], "C")
        self.assertFalse(graded["metrics"]["sorftime_usable"])

    def test_a_requires_sample_gate_and_target_market_amazon(self):
        candidate = self.candidate()
        candidate["sample_gate_status"] = "not_checked"
        self.assertEqual(rank.grade_candidate(candidate)["grade"], "B")
        candidate["sample_gate_status"] = "passed"
        candidate["requested_market"] = "UK"
        graded = rank.grade_candidate(candidate)
        self.assertEqual(graded["grade"], "B")
        self.assertEqual(graded["metrics"]["amazon_pain_evidence_count"], 0)

    def test_reddit_one_parent_cannot_be_promoted_by_manual_status(self):
        candidate = self.candidate()
        candidate["trend_evidence"][0] = {
            "platform": "Reddit", "source_id": "r1", "url": "https://old.reddit.com/r/test/comments/p1",
            "observed_at": "2026-08-25T00:00:00Z", "query_semantic_status": "matched",
        }
        candidate["pain_evidence"] = [
            {"platform": "Reddit", "source_id": f"c{i}", "text_raw": "pain", "url": f"https://old.reddit.com/c{i}", "context": {"post_id": "t3_p1"}}
            for i in range(25)
        ]
        candidate["reddit_sample_gate_status"] = "deep_passed"
        candidate["reddit_sample_gate_detail"] = {"relevant_posts": 1, "parent_posts": 1, "comment_rows": 25}
        graded = rank.grade_candidate(candidate)
        self.assertEqual(graded["grade"], "C")
        self.assertFalse(graded["metrics"]["reddit_quick_gate_passed"])
        self.assertFalse(graded["metrics"]["reddit_deep_gate_passed"])
        self.assertEqual(graded["metrics"]["pain_parent_cluster_count"], 0)

    def test_reddit_quick_gate_does_not_require_comment_collection(self):
        candidate = self.candidate()
        candidate["trend_evidence"][0] = {
            "platform": "Reddit", "source_id": "r1", "url": "https://old.reddit.com/r/test/comments/p1",
            "observed_at": "2026-08-25T00:00:00Z", "query_semantic_status": "matched",
        }
        candidate["reddit_sample_gate_status"] = "quick_passed"
        candidate["reddit_sample_gate_detail"] = {
            "relevant_posts": 10, "parent_posts": 10, "comment_parent_posts": 0, "comment_rows": 0,
        }
        graded = rank.grade_candidate(candidate)
        self.assertTrue(graded["metrics"]["reddit_quick_gate_passed"])
        self.assertFalse(graded["metrics"]["reddit_deep_gate_passed"])
        self.assertIn("Reddit", graded["metrics"]["trend_platforms"])

    def test_reddit_validation_dedupes_native_id_and_prefers_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            visible = root / "reddit_visible.jsonl"
            api = root / "reddit_api.jsonl"
            visible.write_text(json.dumps({"platform": "Reddit", "native_id": "t1_same", "source_id": "visible", "context": {"content_type": "comment", "collection_mode": "visible_dom"}}) + "\n", encoding="utf-8")
            api.write_text(json.dumps({"platform": "Reddit", "native_id": "t1_same", "source_id": "api", "context": {"content_type": "comment", "collection_mode": "oauth_api"}}) + "\n", encoding="utf-8")
            rows = validate.dedupe_reddit_rows([visible, api])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows["t1_same"]["source_id"], "api")

    def test_only_top_or_ab_candidates_require_tiktok_gate_analysis(self):
        self.assertTrue(validate.candidate_needs_tiktok_gate({"priority_order": 1, "grade": "C"}))
        self.assertTrue(validate.candidate_needs_tiktok_gate({"priority_order": 3, "grade": "B"}))
        self.assertFalse(validate.candidate_needs_tiktok_gate({"priority_order": 3, "grade": "C"}))

    def test_report_image_urls_reject_local_and_private_networks(self):
        self.assertEqual(render.safe_url("file:///tmp/product.png"), "")
        self.assertEqual(render.safe_url("http://localhost/product.png"), "")
        self.assertEqual(render.safe_url("http://127.0.0.1/product.png"), "")
        self.assertEqual(render.safe_url("http://169.254.169.254/latest/meta-data"), "")
        self.assertEqual(render.safe_url("http://10.0.0.1/product.png"), "")
        self.assertEqual(render.safe_url("https://example.com/product.png"), "https://example.com/product.png")

    def test_visible_reddit_normalizer_accepts_search_and_legacy_comment_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            search = root / "search.json"
            thread = root / "thread.json"
            search.write_text(json.dumps({
                "schema_version": "visible-search-1.0", "query": "drawer organizer",
                "source_url": "https://old.reddit.com/search?q=drawer+organizer",
                "collected_at": "2026-08-25T00:00:00Z", "requested_market": "US",
                "results": [{"postId": "abc123", "title": "Drawer organizer help", "body": "Bins slide around", "url": "https://old.reddit.com/r/test/comments/abc123/x", "subreddit": "r/test", "commentsText": "12 comments"}],
            }), encoding="utf-8")
            thread.write_text(json.dumps({
                "schema_version": "visible-dom-1.0", "query": "drawer organizer",
                "source_url": "https://old.reddit.com/r/test/comments/abc123/x",
                "collected_at": "2026-08-25T00:00:00Z", "requested_market": "US",
                "post": {"native_id": "t3_abc123", "title": "Drawer organizer help", "text": "Bins slide around", "subreddit": "test", "permalink": "/r/test/comments/abc123/x"},
                "items": [{"native_id": "t1_def456", "parent_native_id": "t3_abc123", "text": "Use rubber feet", "permalink": "/r/test/comments/abc123/x/def456"}],
            }), encoding="utf-8")
            rows, summary = reddit_visible_normalize.normalize([search, thread], ["drawer"], requested_market="US")
            self.assertEqual(summary["package_failures"], [])
            self.assertEqual(summary["unique_posts"], 1)
            self.assertEqual(summary["unique_comments"], 1)
            self.assertEqual({row["native_id"] for row in rows}, {"t3_abc123", "t1_def456"})

    def test_audit_export_selects_latest_normalized_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            raw = run / "data" / "raw"
            raw.mkdir(parents=True)
            stale = raw / "tiktok_multi_2026-08-24.jsonl"
            current = raw / "tiktok_2026-08-24.jsonl"
            stale.write_text("{}\n", encoding="utf-8")
            current.write_text("{}\n", encoding="utf-8")
            stale.touch()
            current.touch()
            self.assertEqual(export.selected_normalized_files(run, "tiktok"), [current])

    def test_multiple_login_sessions_accept_per_source_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            brief_dir = run_dir / "00-research-brief"
            brief_dir.mkdir()
            brief = {
                "requested_market": "US", "target_sales_platform": "Amazon", "broad_category": "Pet Supplies",
                "output_location": str(run_dir),
                "login_session_candidates": [{"session_id": "browser-1"}, {"session_id": "browser-2"}],
                "login_session_selection": {
                    "mode": "per_source",
                    "mapping": {"google_trends": "browser-1", "tiktok": "browser-2"},
                },
            }
            (brief_dir / "research_brief.json").write_text(json.dumps(brief), encoding="utf-8")
            result = validate.validate(run_dir, 2, 5)
            self.assertNotIn("multiple_login_sessions_require_user_selection", result["errors"])

    def test_non_us_other_category_does_not_leak_example_copy(self):
        candidate = self.candidate()
        candidate.update({
            "theme": "dog cooling mat",
            "theme_zh": "宠物降温垫",
            "product_hypothesis": {
                "direction": "可拆洗、耐抓挠的分区降温垫",
                "target_user": "夏季养犬家庭",
                "scenario": "室内休息和短途出行",
                "counter_evidence": "冬季需求可能回落",
                "questions": ["降温持续时间是否足够", "表层是否耐抓挠"],
            },
        })
        candidate["trend_evidence"][1]["metrics"] = {
            "weeks": 26, "recent_4w_mean": 42.0, "prior_4w_mean": 37.39,
            "recent_change_pct": 12.33,
        }
        candidate["sorftime"] = {
            "status": "validated", "category_match": "exact",
            "data": {"top100_monthly_sales_volume": "120000", "new_product_3m_sales_share": "2.10%"},
        }
        graded = rank.grade_candidate(candidate)
        pool = {"candidates": [graded]}
        data = {
            "brief": {"requested_market": "UK", "market_label_zh": "英国市场", "target_sales_platform": "TikTok Shop", "amazon_site": "UK", "language": "en", "broad_category": "Pet Supplies", "broad_category_zh": "宠物用品", "seed_terms": ["dog cooling mat", "pet water bottle"]},
            "trends": {"observed_market": "UK", "series": [{"name": "dog cooling mat", "values": [{"value": 42}] * 26}]},
            "tiktok": [], "tiktok_signals": [],
            "products": [], "pains": {"_meta": {"total_reviews": 0, "low_star_reviews": 0}, "themes": []},
            "calls": [], "amazon": [],
        }
        report_html = render.render_html(pool, data, render.build_evidence_index(pool["candidates"]))
        report_markdown = render.render_markdown(pool, data)
        combined = report_html + report_markdown
        self.assertIn("英国市场", combined)
        self.assertIn("TikTok Shop", combined)
        self.assertIn("宠物降温垫", combined)
        self.assertIn("+12.33%", combined)
        self.assertNotIn("抽屉收纳", combined)
        self.assertNotIn("5.59%", combined)
        self.assertNotIn("美国市场", combined)
        self.assertEqual(render.amazon_product_url("B000TEST", "UK"), "https://www.amazon.co.uk/dp/B000TEST")

    def test_render_and_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            brief_dir = run_dir / "00-research-brief"
            analysis_dir = run_dir / "analysis"
            report_dir = run_dir / "report"
            brief_dir.mkdir()
            analysis_dir.mkdir()
            pool = {"candidates": [rank.grade_candidate(self.candidate())]}
            (brief_dir / "research_brief.json").write_text(json.dumps({"requested_market": "US", "target_sales_platform": "Amazon", "broad_category": "Home Organization", "output_location": str(run_dir)}), encoding="utf-8")
            (analysis_dir / "opportunity_pool.json").write_text(json.dumps(pool), encoding="utf-8")
            evidence = render.build_evidence_index(pool["candidates"])
            report_dir.mkdir()
            data = {
                "trends": {"series": []},
                "tiktok": [],
                "tiktok_signals": [],
                "products": [],
                "pains": {"_meta": {"total_reviews": 0, "low_star_reviews": 0}, "themes": []},
                "calls": [],
                "amazon": [],
            }
            (analysis_dir / "amazon_pain_stats.json").write_text(json.dumps(data["pains"]), encoding="utf-8")
            (analysis_dir / "tiktok_sample_gates.json").write_text(json.dumps({"themes": {"Drawer organizer": {
                "status": "deep_passed", "relevant_videos": 20, "accounts": 5,
                "comment_parent_videos": 5, "comment_rows": 100,
                "quick_gate_passed": True, "deep_gate_passed": True,
            }}}), encoding="utf-8")
            report_markdown = render.render_markdown(pool, data)
            report_html = render.render_html(pool, data, evidence)
            self.assertIn("arrived cracked", report_html)
            self.assertIn("看完后，你可以继续问我", report_html)
            section_positions = [report_html.find(f'id="{section_id}"') for section_id in validate.REPORT_SECTION_IDS]
            self.assertNotIn(-1, section_positions)
            self.assertEqual(section_positions, sorted(section_positions))
            self.assertIn('text-anchor="end"', render.svg_hbars([("A", 10, "10 月销 · 20 评")], "test", "#000"))
            (report_dir / "report.md").write_text(report_markdown, encoding="utf-8")
            (report_dir / "report.html").write_text(report_html, encoding="utf-8")
            staging_dir = run_dir / "work" / "workbook-sources"
            staging_dir.mkdir(parents=True)
            for csv_name, _ in validate.WORKBOOK_SHEETS:
                (staging_dir / csv_name).write_text("source_id\n", encoding="utf-8")
            self.write_minimal_workbook(report_dir / "research_data.xlsx", [name for _, name in validate.WORKBOOK_SHEETS])
            (analysis_dir / "evidence_index.json").write_text(json.dumps(evidence), encoding="utf-8")
            result = validate.validate(run_dir, 3, 5)
            self.assertTrue(result["ok"], result)

    def test_start_card_requires_market_platform_category_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            brief_dir = run_dir / "00-research-brief"
            brief_dir.mkdir()
            (brief_dir / "research_brief.json").write_text(json.dumps({"requested_market": "US"}), encoding="utf-8")
            result = validate.validate(run_dir, 2, 5)
            self.assertIn("missing_business_card_fields:target_sales_platform,broad_category,output_location", result["errors"])

    def test_multiple_login_sessions_require_explicit_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            brief_dir = run_dir / "00-research-brief"
            brief_dir.mkdir()
            brief = {
                "requested_market": "US", "target_sales_platform": "Amazon", "broad_category": "Pet Supplies",
                "output_location": str(run_dir),
                "login_session_candidates": [{"session_id": "browser-1"}, {"session_id": "browser-2"}],
            }
            (brief_dir / "research_brief.json").write_text(json.dumps(brief), encoding="utf-8")
            result = validate.validate(run_dir, 2, 5)
            self.assertIn("multiple_login_sessions_require_user_selection", result["errors"])
            brief["login_session_selection"] = {"mode": "single", "session_id": "browser-2"}
            (brief_dir / "research_brief.json").write_text(json.dumps(brief), encoding="utf-8")
            result = validate.validate(run_dir, 2, 5)
            self.assertNotIn("multiple_login_sessions_require_user_selection", result["errors"])

    def test_tiktok_metric_and_url_normalization(self):
        self.assertEqual(tiktok.parse_metric("12.3K views"), 12300)
        self.assertEqual(tiktok.parse_metric("1.2万"), 12000)
        self.assertEqual(tiktok.normalize_url("/@creator/video/123?lang=en"), "https://www.tiktok.com/@creator/video/123")

    def test_tiktok_query_plan_is_bounded(self):
        plan = tiktok_plan.build_plan(
            [{"query": "drawer organizer", "market": "US", "language": "en"}],
            {"market": "unspecified", "language": "unspecified", "max_videos": 10, "max_comment_videos": 3, "max_comments_per_video": 30},
        )
        self.assertEqual(plan["totals"]["queries"], 1)
        self.assertEqual(plan["totals"]["max_comments"], 90)

    def test_tiktok_source_packages_normalize_to_video_and_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            discover = {
                "schema_version": "1.0", "mode": "discover", "query": "drawer organizer",
                "requested_market": "US", "observed_market": "unknown", "language": "en",
                "collected_at": "2026-08-24T10:00:00+08:00", "source_url": "https://www.tiktok.com/search?q=drawer%20organizer",
                "stop_reason": "sample_cap", "items": [{"content_type": "video", "native_id": "v1", "url": "https://www.tiktok.com/@u/video/v1", "text": "Drawer organizer test", "engagement": {"views": "1.2K"}}],
            }
            comments = {
                "schema_version": "1.0", "mode": "comments", "query": "drawer organizer",
                "requested_market": "US", "observed_market": "unknown", "language": "en",
                "collected_at": "2026-08-24T10:05:00+08:00", "source_url": "https://www.tiktok.com/@u/video/v1",
                "stop_reason": "sample_cap", "items": [{"content_type": "comment", "native_id": "c1", "parent_video_id": "v1", "video_url": "https://www.tiktok.com/@u/video/v1", "text": "The dividers keep slipping", "engagement": {"likes": "12"}}],
            }
            p1, p2 = root / "discover.json", root / "comments.json"
            p1.write_text(json.dumps(discover), encoding="utf-8")
            p2.write_text(json.dumps(comments), encoding="utf-8")
            rows, summary = tiktok_normalize.normalize_packages([p1, p2], ["dividers"])
            self.assertEqual(summary["video_rows"], 1)
            self.assertEqual(summary["comment_rows"], 1)
            comment = next(row for row in rows if row["content_type"] == "comment")
            self.assertEqual(comment["keyword_hit"], ["dividers"])
            self.assertEqual(comment["engagement"]["likes"], 12)

    def test_tiktok_gate_requires_reviewed_videos_and_parent_comments(self):
        rows = []
        relevance = {}
        for index in range(20):
            source_id = f"v{index}"
            native_id = f"n{index}"
            rows.append({"platform": "TikTok", "content_type": "video", "source_id": source_id, "native_id": native_id, "text_raw": "video", "context": {"author_handle": f"creator{index % 5}"}})
            relevance[source_id] = {"source_id": source_id, "theme": "cat litter mat", "query_semantic_status": "matched"}
        for index in range(100):
            rows.append({"platform": "TikTok", "content_type": "comment", "source_id": f"c{index}", "text_raw": "comment", "context": {"parent_video_id": f"n{index % 5}"}})
        gate = tiktok_analyze.analyze_rows(rows, relevance)["themes"]["cat litter mat"]
        self.assertTrue(gate["deep_gate_passed"])
        self.assertEqual(gate["comment_parent_videos"], 5)

    def test_reddit_analyzer_dedupes_native_ids_and_flags_concentration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = []
            for parent in ("t3_p1", "t3_p2", "t3_p3"):
                rows.append({"platform": "Reddit", "native_id": parent, "source_id": parent, "text_raw": "post", "context": {"content_type": "post", "collection_mode": "visible_dom"}})
            for index in range(60):
                parent = "t3_p1" if index < 40 else "t3_p2" if index < 50 else "t3_p3"
                rows.append({"platform": "Reddit", "native_id": f"t1_c{index}", "source_id": f"c{index}", "text_raw": "comment", "context": {"content_type": "comment", "post_id": parent, "collection_mode": "visible_dom"}})
            rows.append({"platform": "Reddit", "native_id": "t1_c0", "source_id": "api-duplicate", "text_raw": "comment from api", "context": {"content_type": "comment", "post_id": "t3_p1", "collection_mode": "oauth_api"}})
            source = root / "reddit.jsonl"
            source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            relevance = root / "relevance.tsv"
            relevance.write_text("native_id\ttheme\tquery_semantic_status\n" + "".join(f"t3_p{i}\tcat litter mat\tmatched\n" for i in range(1, 6)), encoding="utf-8")
            loaded = reddit_analyze.load_rows([str(source)])
            self.assertEqual(len(loaded), 63)
            self.assertEqual(next(row for row in loaded if row["native_id"] == "t1_c0")["context"]["collection_mode"], "oauth_api")

    def test_reddit_comments_cannot_pass_without_collected_parent_posts(self):
        rows = [
            {"platform": "Reddit", "native_id": f"t1_c{index}", "text_raw": "comment", "context": {"content_type": "comment", "post_id": f"t3_p{index % 3 + 1}", "collection_mode": "visible_dom"}}
            for index in range(60)
        ]
        relevance = {
            f"t3_p{index}": {"native_id": f"t3_p{index}", "theme": "cat litter mat", "query_semantic_status": "matched"}
            for index in range(1, 4)
        }
        payload = reddit_analyze.analyze_rows(rows, relevance)
        self.assertEqual(payload["themes"], {})
        self.assertEqual(payload["matched_parent_posts"], 3)
        self.assertEqual(payload["collected_matched_parent_posts"], 0)

    def test_sorftime_page_four_requires_user_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            sorftime_dir = run_dir / "sorftime"
            sorftime_dir.mkdir()
            (sorftime_dir / "call_log.jsonl").write_text(json.dumps({"tool": "product_search", "arguments": {"page": 4}}) + "\n", encoding="utf-8")
            result = validate.validate(run_dir, 2, 5)
            self.assertIn("call_1:product_search:page_4_requires_user_approval", result["errors"])

    def test_sorftime_products_merge_all_pages_and_dedupe_asin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page1 = root / "cat_products_page001.json"
            page2 = root / "cat_products_page002.json"
            page1.write_text(json.dumps({"data": [{"asin": "A1", "title": "First", "price": 10}]}), encoding="utf-8")
            page2.write_text(json.dumps({"data": [{"asin": "A1", "title": "Duplicate", "review_count": 50}, {"asin": "A2", "title": "Second"}]}), encoding="utf-8")
            report_rows = render.load_sorftime_products([page1, page2])
            export_rows = export.load_sorftime_products([page1, page2], root)
            self.assertEqual([row["asin"] for row in report_rows], ["A1", "A2"])
            self.assertEqual([row["asin"] for row in export_rows], ["A1", "A2"])
            self.assertEqual(report_rows[0]["title"], "First")
            self.assertEqual(report_rows[0]["review_count"], 50)

    def test_reddit_api_empty_does_not_hide_route_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            plan.write_text(json.dumps({"requests": [
                {"url": "https://www.reddit.com/search.json?q=first", "output": str(root / "first_page001.json"), "query": "first"},
                {"url": "https://www.reddit.com/search.json?q=second", "output": str(root / "second_page001.json"), "query": "second"},
            ]}), encoding="utf-8")
            args = Namespace(plan=plan, manifest=root / "manifest.jsonl", failure_log=root / "failures.jsonl", summary=root / "summary.json", max_pages=1, user_agent="test", timeout=1)
            empty = {"data": {"children": [], "after": None}}
            with patch.object(reddit_api, "fetch_with_fallback", side_effect=[(None, {}, [{"reason": "blocked"}]), (empty, {"url": "https://www.reddit.com/search.json?q=second", "http_status": 200, "source_route": "public_json_api"}, [])]):
                code = reddit_api.search(args, [{"name": "public_json_api"}], [])
            summary = json.loads(args.summary.read_text(encoding="utf-8"))
            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "partial")

    def test_reddit_public_routes_leave_old_reddit_to_logged_in_browser(self):
        routes, failures = reddit_api.route_specs("public", "test", 1)
        self.assertEqual(failures, [])
        self.assertEqual(routes, [{"name": "public_json_api", "host": "www.reddit.com", "token": ""}])

    def test_reddit_json_error_payload_is_not_treated_as_empty(self):
        error = reddit_api.payload_error({"error": 403, "message": "Forbidden"})
        self.assertEqual(error["reason"], "json_error_response")
        self.assertIsNone(reddit_api.payload_error({"kind": "Listing", "data": {"children": [], "after": None}}))

    def test_reddit_retry_failure_is_preserved_after_success(self):
        route = {"name": "public_json_api", "host": "www.reddit.com", "token": ""}
        payload = {"data": {"children": [], "after": None}}
        meta = {"url": "https://www.reddit.com/search.json?q=x", "http_status": 200, "source_route": "public_json_api", "attempt": 2, "_attempt_failures": [{"reason": "http_error", "http_status": 429, "attempt": 1}]}
        with patch.object(reddit_api, "fetch_json", return_value=(payload, meta)):
            actual, _, failures = reddit_api.fetch_with_fallback("https://www.reddit.com/search.json?q=x", [route], "test", 1)
        self.assertEqual(actual, payload)
        self.assertEqual(failures[0]["http_status"], 429)

    def test_reddit_raw_response_bytes_and_exact_text_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "raw.json"
            body = b'{ "kind": "Listing", "data": {"children": [], "after": null} }\n'
            size, digest = reddit_api.write_raw_response(output, {}, {"_raw_body": body})
            self.assertEqual(output.read_bytes(), body)
            self.assertEqual(size, len(body))
            self.assertEqual(len(digest), 64)
        meta = {"lang": "EN", "query": "x", "_resolved_file": "raw.json", "source_route": "oauth_api"}
        post = reddit_normalize.post_row({"name": "t3_abc", "title": "  title  ", "selftext": " body\n"}, meta, [])
        comment = reddit_normalize.comment_row({"name": "t1_abc", "body": "  exact body\n"}, meta, {"name": "t3_abc"}, [])
        self.assertEqual(post["text_raw"], "  title  \n\n body\n")
        self.assertEqual(comment["text_raw"], "  exact body\n")

    def test_visible_dom_duplicate_packages_do_not_inflate_parent_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = {
                "schema_version": "visible-dom-1.0", "source_url": "https://old.reddit.com/r/test/comments/p1/thread/",
                "query": "cat litter mat", "requested_market": "US", "lang": "EN", "round": 1,
                "collected_at": "2026-08-25T00:00:00Z", "stop_reason": "visible_end", "json_route_status": "blocked_by_client",
                "post": {"native_id": "t3_p1", "title": "title", "text": "body"},
                "items": [{"native_id": "t1_c1", "parent_native_id": "t3_p1", "text": " comment "}],
            }
            first, second = root / "first.json", root / "second.json"
            first.write_text(json.dumps(package), encoding="utf-8")
            second.write_text(json.dumps(package), encoding="utf-8")
            output, summary = root / "rows.jsonl", root / "summary.json"
            result = subprocess.run([
                "python3", str(ROOT / "scripts" / "bggg_data_reddit_visible_normalize.py"),
                "--inputs", str(first), str(second), "--output", str(output), "--summary", str(summary),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            stats = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(stats["unique_comments"], 1)
            self.assertEqual(stats["comment_rows_by_parent"], {"t3_p1": 1})


if __name__ == "__main__":
    unittest.main()
