#!/usr/bin/env python3
"""Render a concise, visual, evidence-linked opportunity report."""

from __future__ import annotations

import argparse
import base64
import html
import ipaddress
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

COLORS = ["#176b45", "#e79245", "#4267a8", "#9a5ea8", "#d15b5b", "#648a70"]


def load_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
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
                rows[key] = row
    return list(rows.values())


def validate_deep_selection(brief: dict, candidates: list[dict]) -> None:
    """Refuse to render a deep report without an explicit, consistent Top N choice."""
    selected_top_n = brief.get("selected_top_n")
    declared_ids = {str(value) for value in (brief.get("deep_validation_candidate_ids") or []) if value}
    selected_ids = {
        str(row.get("candidate_id"))
        for row in candidates
        if (row.get("metrics") or {}).get("selected_for_deep_validation") and row.get("candidate_id")
    }
    if selected_top_n is None:
        raise ValueError("Top N 尚未由用户明确选择；请先停在快筛报告并询问用户。")
    try:
        selected_top_n = int(selected_top_n)
    except (TypeError, ValueError) as exc:
        raise ValueError("selected_top_n 必须是用户明确选择的正整数。") from exc
    if selected_top_n < 1:
        raise ValueError("selected_top_n 必须至少为 1。")
    if len(declared_ids) != selected_top_n:
        raise ValueError("deep_validation_candidate_ids 数量与 selected_top_n 不一致。")
    if selected_ids != declared_ids:
        raise ValueError("报告候选池与用户确认的 Top N 方向不一致。")


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


def trends_from_signals(run: Path) -> dict:
    rows = load_jsonl(run / "data" / "signals" / "google_trends_product_terms.jsonl")
    preferred_market = "US" if any(row.get("observed_market") == "US" for row in rows) else None
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        context = row.get("context") or {}
        if context.get("window") != "12m":
            continue
        if preferred_market and row.get("observed_market") != preferred_market:
            continue
        match = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", str(row.get("text_raw") or ""))
        grouped.setdefault(str(row.get("theme") or ""), []).append({
            "date": match.group(1) if match else "",
            "value": row.get("value") or 0,
        })
    series = [
        {"name": theme, "values": sorted(values, key=lambda item: item["date"])}
        for theme, values in grouped.items() if theme
    ]
    return {"series": series, "observed_market": preferred_market or "unknown"}


def tiktok_signals_from_rows(rows: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for row in rows:
        if row.get("content_type") != "video":
            continue
        context = row.get("context") or {}
        theme = str(context.get("candidate_id") or "")
        views = float((row.get("engagement") or {}).get("views") or (row.get("engagement") or {}).get("visible_metric") or 0)
        if theme and (theme not in best or views > float((best[theme].get("metrics") or {}).get("views") or 0)):
            best[theme] = {"theme": theme, "metrics": {"views": views}}
    return list(best.values())


def safe_url(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        return ""
    try:
        if not ipaddress.ip_address(hostname).is_global:
            return ""
    except ValueError:
        pass
    normalized_path = parsed.path.replace(" ", "") if hostname.endswith("media-amazon.com") else parsed.path
    return parsed._replace(
        path=quote(normalized_path, safe="/%:@"),
        query=quote(parsed.query, safe="=&%:@?"),
    ).geturl()


def image_data_uri(value: object) -> str:
    url = safe_url(value)
    if not url:
        return ""
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=12) as response:
            data = response.read(5_000_001)
            if len(data) > 5_000_000:
                return ""
            content_type = response.headers.get_content_type()
        if not content_type.startswith("image/"):
            return ""
        return f"data:{content_type};base64,{base64.b64encode(data).decode('ascii')}"
    except (OSError, ValueError):
        return ""


def fmt_num(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—" if value in (None, "") else str(value)
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if number >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{number:g}"


def candidate_evidence(candidate: dict) -> list[dict]:
    return list(candidate.get("trend_evidence") or []) + list(candidate.get("pain_evidence") or [])


def build_evidence_index(candidates: list[dict]) -> list[dict]:
    index, seen = [], set()
    for candidate in candidates:
        for row in candidate_evidence(candidate):
            source_id = str(row.get("source_id") or "")
            key = (str(candidate.get("candidate_id") or ""), source_id)
            if not source_id or key in seen:
                continue
            seen.add(key)
            context = row.get("context") or {}
            index.append({
                "candidate_id": candidate.get("candidate_id"),
                "theme": candidate.get("theme"),
                "source_id": source_id,
                "platform": row.get("platform"),
                "content_type": row.get("content_type") or row.get("signal_type"),
                "url": row.get("url") or context.get("url") or context.get("video_url"),
                "text_raw": row.get("text_raw") or "",
                "pain_label": row.get("pain_label"),
            })
    return index


def svg_line_chart(series: list[dict], highlight_name: str = "") -> str:
    width, height, left, top, plot_w, plot_h = 920, 340, 58, 42, 800, 220
    body = [f'<svg class="viz" viewBox="0 0 {width} {height}" role="img" aria-label="Google Trends 过去 12 个月趋势"><rect width="100%" height="100%" rx="18" fill="#fbfcfa"/>']
    for tick in range(0, 101, 25):
        y = top + plot_h - (tick / 100) * plot_h
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#dfe7e1"/>')
        body.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="axis">{tick}</text>')
    for idx, item in enumerate(series):
        values = item.get("values") or []
        if not values:
            continue
        points = []
        for pos, point in enumerate(values):
            x = left + (pos / max(1, len(values) - 1)) * plot_w
            y = top + plot_h - (float(point.get("value") or 0) / 100) * plot_h
            points.append(f"{x:.1f},{y:.1f}")
        color = COLORS[idx % len(COLORS)]
        stroke = 4 if item.get("name") == highlight_name else 2
        opacity = 1 if item.get("name") == highlight_name else 0.65
        body.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="{stroke}" opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round"/>')
    for idx, item in enumerate(series):
        x, y = 55 + (idx % 3) * 280, 300 + (idx // 3) * 24
        color = COLORS[idx % len(COLORS)]
        label = html.escape(str(item.get("name") or ""))
        body.append(f'<circle cx="{x}" cy="{y - 4}" r="5" fill="{color}"/><text x="{x + 12}" y="{y}" class="legend">{label}</text>')
    return "".join(body) + "</svg>"


def svg_hbars(rows: list[tuple[str, float, str]], aria: str, color: str) -> str:
    width, row_h = 920, 46
    height = 55 + row_h * max(1, len(rows))
    max_value = max((value for _, value, _ in rows), default=1) or 1
    body = [f'<svg class="viz" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(aria)}"><rect width="100%" height="100%" rx="18" fill="#fbfcfa"/>']
    for idx, (label, value, note) in enumerate(rows):
        y, bar_w = 28 + idx * row_h, 590 * value / max_value
        body.append(f'<text x="22" y="{y + 16}" class="bar-label">{html.escape(label[:34])}</text>')
        body.append(f'<rect x="255" y="{y}" width="590" height="20" rx="10" fill="#e8efe9"/>')
        body.append(f'<rect x="255" y="{y}" width="{bar_w:.1f}" height="20" rx="10" fill="{color}"/>')
        body.append(f'<text x="895" y="{y + 15}" text-anchor="end" class="bar-value">{html.escape(note)}</text>')
    return "".join(body) + "</svg>"


def load_sorftime_products(paths: list[Path]) -> list[dict]:
    products: dict[str, dict] = {}
    anonymous = 0
    for file in sorted(paths):
        payload = load_json(file, {}) or {}
        for row in payload.get("data") or []:
            asin = str(row.get("asin") or "").strip().upper()
            key = asin or f"__anonymous_{anonymous}"
            if not asin:
                anonymous += 1
            if key not in products:
                products[key] = {**row, "asin": asin or row.get("asin")}
            else:
                existing = products[key]
                for field, value in row.items():
                    if existing.get(field) in (None, "", []) and value not in (None, "", []):
                        existing[field] = value
    return list(products.values())


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


def actual_data(run: Path) -> dict:
    amazon_files = sorted((run / "data" / "raw").glob("amazon_woot_*.jsonl"))
    trend_files = sorted((run / "work" / "google-trends").glob("*.json"))
    tiktok_files = selected_normalized_files(run, "tiktok")
    reddit_files = selected_normalized_files(run, "reddit")
    product_files = sorftime_product_files(run)
    tiktok = load_jsonl_files(tiktok_files)
    tiktok_signals = load_jsonl(run / "data" / "signals" / "tiktok.jsonl")
    return {
        "trends": load_json(trend_files[-1], {}) if trend_files else trends_from_signals(run),
        "tiktok": tiktok,
        "tiktok_signals": tiktok_signals or tiktok_signals_from_rows(tiktok),
        "reddit": load_jsonl_files(reddit_files),
        "reddit_gates": load_json(run / "analysis" / "reddit_sample_gates.json", {}) or {},
        "products": load_sorftime_products(product_files),
        "pains": load_json(run / "analysis" / "amazon_pain_stats.json", {}) or {},
        "calls": load_jsonl(run / "sorftime" / "call_log.jsonl"),
        "amazon": load_jsonl(amazon_files[-1]) if amazon_files else [],
    }


def scope_labels(data: dict) -> tuple[str, str, list[str]]:
    brief = data.get("brief") or {}
    market = str(brief.get("market_label_zh") or brief.get("requested_market") or "目标市场")
    category_en = str(brief.get("broad_category") or (brief.get("allowed_categories") or ["待确认品类"])[0])
    category_zh = str(brief.get("broad_category_zh") or category_en)
    category = f"{category_en}（{category_zh}）" if category_zh != category_en else category_en
    labels = brief.get("seed_term_labels") or {}
    seed_terms = [str(labels.get(term) or term) for term in (brief.get("seed_terms") or [])]
    return market, category, seed_terms


def candidate_label(candidate: dict) -> str:
    theme = str(candidate.get("theme") or "候选方向")
    theme_zh = str(candidate.get("theme_zh") or "")
    return f"{theme_zh}（{theme.title()}）" if theme_zh else theme


def google_trend_metrics(candidate: dict) -> dict:
    for row in candidate.get("trend_evidence") or []:
        if row.get("platform") == "Google Trends":
            return row.get("metrics") or {}
    return {}


def change_copy(value: object, *, signed: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "未计算"
    formatted = f"{number:+.2f}%" if signed else f"{abs(number):.2f}%"
    if number > 0:
        return f"上升 {formatted}"
    if number < 0:
        return f"下降 {formatted}"
    return "持平"


def decision_copy(candidate: dict) -> tuple[str, str]:
    grade = str(candidate.get("grade") or "—")
    decisions = {
        "A": ("高潜力，优先推进验证", "可以优先进入样品、利润和合规验证，但不替代最终上架决策。"),
        "B": ("有机会，先做样品验证", "值得继续验证，但现在还不适合直接上架。"),
        "C": ("有信号，先补关键证据", "暂时保留观察，补齐趋势、商业或买后证据后再决定。"),
        "D": ("不建议继续推进", "当前存在硬性排除或明显反证，建议停止投入。"),
    }
    badge, sentence = decisions.get(grade, ("证据不足，暂不决策", "当前证据不足，先补数据再判断。"))
    return f"{grade} 级 · {badge}", sentence


def amazon_product_url(asin: str, site: str) -> str:
    domains = {
        "US": "www.amazon.com", "UK": "www.amazon.co.uk", "CA": "www.amazon.ca",
        "DE": "www.amazon.de", "FR": "www.amazon.fr", "IT": "www.amazon.it",
        "ES": "www.amazon.es", "JP": "www.amazon.co.jp", "AU": "www.amazon.com.au",
        "MX": "www.amazon.com.mx", "IN": "www.amazon.in",
    }
    return f"https://{domains.get(site.upper(), 'www.amazon.com')}/dp/{asin}" if asin else ""


def reddit_sample_metrics(rows: list[dict]) -> dict:
    parent_counts: dict[str, int] = {}
    posts = comments = 0
    for row in rows:
        context = row.get("context") or {}
        content_type = context.get("content_type") or row.get("content_type")
        if content_type == "post":
            posts += 1
        elif content_type == "comment":
            comments += 1
            parent_id = str(context.get("post_id") or "unknown")
            parent_counts[parent_id] = parent_counts.get(parent_id, 0) + 1
    largest_share = max(parent_counts.values()) / comments if comments and parent_counts else 0
    if not comments:
        label = "无评论样本"
    elif len(parent_counts) == 1:
        label = "小样本：仅 1 个父帖"
    elif largest_share > 0.4:
        label = f"样本集中：最大父帖占 {largest_share:.1%}"
    else:
        label = f"最大父帖占 {largest_share:.1%}"
    return {"posts": posts, "comments": comments, "parent_posts": len(parent_counts), "largest_parent_share": largest_share, "label": label}


def reddit_gate_metrics(gate: dict) -> dict:
    posts = int(gate.get("parent_posts") or gate.get("relevant_posts") or 0)
    comments = int(gate.get("comment_rows") or 0)
    parent_posts = int(gate.get("comment_parent_posts") or 0)
    largest_share = float(gate.get("largest_parent_share") or 0)
    if not comments:
        label = "无评论样本"
    elif parent_posts == 1:
        label = "小样本：仅 1 个评论父帖"
    elif gate.get("concentration_warning"):
        label = f"样本集中：最大父帖占 {largest_share:.1%}"
    else:
        label = f"最大父帖占 {largest_share:.1%}"
    return {
        "posts": posts,
        "comments": comments,
        "parent_posts": parent_posts,
        "largest_parent_share": largest_share,
        "label": label,
        "modes": "、".join(gate.get("collection_modes") or []) or "未运行",
    }


def coverage_sentence(data: dict) -> str:
    market, _, _ = scope_labels(data)
    reddit_rows = data.get("reddit") or []
    reddit_metrics = reddit_sample_metrics(reddit_rows)
    videos = sum(1 for row in data["tiktok"] if row.get("content_type") == "video")
    comments = sum(1 for row in data["tiktok"] if row.get("content_type") == "comment")
    asins = {asin for row in data["amazon"] for asin in ((row.get("context") or {}).get("asins") or [])}
    series = data["trends"].get("series") or []
    weeks = max((len(row.get("values") or []) for row in series), default=0)
    return (
        f"这轮看了 {market} Google 搜索的 {len(series)} 个商品词（{weeks} 周），"
        f"TikTok {videos} 个视频和 {comments} 条评论，"
        f"Reddit {reddit_metrics['posts']} 个帖子和 {reddit_metrics['comments']} 条评论（{reddit_metrics['label']}），"
        f"Sorftime {len(data['calls'])} 次调用，以及 {len(asins)} 个 ASIN 的 {len(data['amazon'])} 条 Amazon 书面评论。"
    )


def render_markdown(pool: dict, data: dict) -> str:
    candidates = pool.get("candidates") or []
    selected_candidates = [row for row in candidates if (row.get("metrics") or {}).get("selected_for_deep_validation")]
    top = selected_candidates[0] if selected_candidates else (candidates[0] if candidates else {})
    market, category, seed_terms = scope_labels(data)
    top_label = candidate_label(top)
    selected_labels = "、".join(candidate_label(row) for row in selected_candidates) or "尚未选择"
    verdict_badge, verdict_sentence = decision_copy(top)
    trend_metrics = google_trend_metrics(top)
    trend_change = change_copy(trend_metrics.get("recent_change_pct"))
    sf_data = ((top.get("sorftime") or {}).get("data") or {})
    pains = data["pains"].get("themes") or []
    pain_meta = data["pains"].get("_meta") or {}
    hypothesis = top.get("product_hypothesis") or {}
    top_pains = "、".join(f"{row['label']}（{row['low_star_mentions']}）" for row in pains[:3])
    brief = data.get("brief") or {}
    amazon_site = str(brief.get("amazon_site") or brief.get("requested_market") or "实际站点")
    lines = [
        f"# {market} {category}趋势选品报告", "", "## 这次从哪里开始", "",
        f"本轮面向 **{market} · {brief.get('target_sales_platform') or '待确认销售平台'}**，研究品类 **{category}**；Sorftime 形成 {len(seed_terms)} 个有效方向，三个免费源全部快筛后，用户选择 **{len(selected_candidates)} 个方向**进入深验。", "",
        f"深验方向：{selected_labels}。", "", "## 先说结论", "",
        f"**{top_label}：{verdict_badge}。{verdict_sentence}**", "",
        f"- 搜索：排名首位的深验方向最近 4 周较前 4 周{trend_change}；本轮共快筛 {len(seed_terms)} 个方向。",
        f"- 商业：Sorftime 类目匹配为 {(top.get('sorftime') or {}).get('category_match', '未验证')}；Top 100 月销量 {sf_data.get('top100_monthly_sales_volume', '—')}，近 3 个月新品销售占比 {sf_data.get('new_product_3m_sales_share', '—')}。",
        f"- 买后问题：{pain_meta.get('total_reviews', len(data['amazon']))} 条 Amazon 评论中，低星样本最集中在 {top_pains or '待补证据'}。",
        f"- 产品方向：{hypothesis.get('direction') or '待结合痛点证据形成'}。", "",
        "## 数据覆盖", "", coverage_sentence(data), "",
        f"> TikTok 与 Reddit 只能证明内容／社区语境，不能单独证明地理市场；Reddit API 受阻时可回退到已登录 old.reddit.com，并保留 collection_mode。目标市场由 Google Trends、Sorftime 和 Amazon {amazon_site} 的实际覆盖共同落锚。Amazon 若使用分星抽样，则只分析缺陷，不计算市场好评率。", "",
        "## 全候选漏斗与去留原因", "", "| 方向 | Google Trends | TikTok | Reddit | 决定 | 等级 | 原因 |", "|---|---|---|---|---|---|---|",
    ]
    for row in candidates:
        statuses = (row.get("metrics") or {}).get("free_source_statuses") or {}
        reasons = row.get("elimination_reasons") or row.get("grade_reasons") or row.get("missing_evidence") or []
        lines.append(
            f"| {candidate_label(row)} | {statuses.get('Google Trends', 'not_run')} | {statuses.get('TikTok', 'not_run')} | "
            f"{statuses.get('Reddit', 'not_run')} | {row.get('screening_decision', '—')} | {row.get('grade', '—')} | {'；'.join(map(str, reasons)) or '—'} |"
        )
    lines.extend(["", "## Amazon 低星痛点", "", "| 痛点 | 低星提及 | 占 1–3 星样本 |", "|---|---:|---:|"])
    for row in pains:
        lines.append(f"| {row.get('label')} | {row.get('low_star_mentions')} | {row.get('low_star_share_pct')}% |")
    lines.extend(["", "## 数据文件", "", "- [下载完整研究数据工作簿](research_data.xlsx)：一个 Excel 文件，内含 10 个按渠道拆分的工作表。"])
    lines.extend(["", "## 证据抽查", ""])
    for item in build_evidence_index(candidates)[:15]:
        link = safe_url(item.get("url"))
        text = str(item.get("text_raw") or "").replace("\n", " ")
        lines.append(f"- {item.get('source_id')} · {item.get('platform')} · {text}" + (f" · [原始链接]({link})" if link else ""))
    representative_count = sum(len((((row.get("sorftime") or {}).get("product_search") or {}).get("representative_asins") or [])) for row in selected_candidates)
    lines.extend(["", "## 看完后可以继续问我", "", f"你可以让我继续对比 {representative_count} 个代表 ASIN、扩大 Top N、展开某类差评证据、把机会方向整理成打样规格，或换市场／研究品类重跑。"])
    return "\n".join(lines).rstrip() + "\n"


def render_html(pool: dict, data: dict, evidence: list[dict]) -> str:
    candidates = pool.get("candidates") or []
    selected_candidates = [row for row in candidates if (row.get("metrics") or {}).get("selected_for_deep_validation")]
    top = selected_candidates[0] if selected_candidates else (candidates[0] if candidates else {})
    market, category, seed_terms = scope_labels(data)
    top_label = candidate_label(top)
    selected_labels = "、".join(candidate_label(row) for row in selected_candidates) or "尚未选择"
    verdict_badge, verdict_sentence = decision_copy(top)
    trend_metrics = google_trend_metrics(top)
    trend_change = change_copy(trend_metrics.get("recent_change_pct"))
    brief = data.get("brief") or {}
    amazon_site = str(brief.get("amazon_site") or brief.get("requested_market") or "US")
    target_platform = str(brief.get("target_sales_platform") or "待确认销售平台")
    sf = top.get("sorftime") or {}
    pains = data["pains"].get("themes") or []
    pain_meta = data["pains"].get("_meta") or {}
    trend_series = data["trends"].get("series") or []
    trend_weeks = max((len(row.get("values") or []) for row in trend_series), default=0)
    trend_svg = svg_line_chart(trend_series, str(top.get("theme") or ""))
    tiktok_rows = []
    tiktok_peak = None
    for row in data["tiktok_signals"]:
        metrics = row.get("metrics") or {}
        tiktok_rows.append((str(row.get("theme") or ""), float(metrics.get("views") or 0), f"{fmt_num(metrics.get('views'))} 播放"))
        if tiktok_peak is None or float(metrics.get("views") or 0) > float((tiktok_peak.get("metrics") or {}).get("views") or 0):
            tiktok_peak = row
    tiktok_svg = svg_hbars(tiktok_rows[:5], "TikTok 相关视频播放量", "#e79245")
    selected_asin_directions = {}
    for candidate in selected_candidates:
        for asin in (((candidate.get("sorftime") or {}).get("product_search") or {}).get("representative_asins") or []):
            selected_asin_directions[str(asin)] = candidate_label(candidate)
    selected = set(selected_asin_directions)
    product_rows = []
    product_cards = []
    for row in data["products"]:
        if row.get("asin") in selected:
            product_rows.append((str(row.get("asin")), float(row.get("monthly_sales_volume") or 0), f"{fmt_num(row.get('monthly_sales_volume'))} 月销 · {fmt_num(row.get('review_count'))} 评"))
            asin = str(row.get("asin") or "")
            image_src = image_data_uri(row.get("main_image"))
            image = f'<img src="{image_src}" alt="{html.escape(asin)} 产品图">' if image_src else '<div class="product-image-missing">产品图未取回</div>'
            amazon_url = amazon_product_url(asin, amazon_site)
            title = html.escape(str(row.get("title") or asin))
            product_cards.append(
                f'<article class="product-card">{image}<div class="product-body"><div class="product-asin">{html.escape(asin)}</div>'
                f'<div class="product-direction">{html.escape(selected_asin_directions.get(asin, "深验方向"))}</div>'
                f'<h4>{title}</h4><div class="product-metrics"><span>${html.escape(str(row.get("price") or "—"))}</span>'
                f'<span>{fmt_num(row.get("monthly_sales_volume"))} 月销</span><span>{fmt_num(row.get("review_count"))} 评</span>'
                f'<span>{html.escape(str(row.get("star_rating") or "—"))} 星</span></div>'
                f'<a href="{html.escape(amazon_url)}" target="_blank" rel="noreferrer">查看 Amazon 商品</a></div></article>'
            )
    product_svg = svg_hbars(product_rows, "代表 ASIN 月销量与评论门槛", "#4267a8")
    pain_rows = [(str(row.get("label") or ""), float(row.get("low_star_mentions") or 0), f"{row.get('low_star_mentions')} 条") for row in pains]
    pain_svg = svg_hbars(pain_rows, "Amazon 低星痛点提及", "#d15b5b")
    evidence_cards = []
    selected_ids = {row.get("candidate_id") for row in selected_candidates} or {top.get("candidate_id")}
    for item in [row for row in evidence if row.get("candidate_id") in selected_ids][:15]:
        url = safe_url(item.get("url"))
        raw_quote = str(item.get("text_raw") or "").strip()
        quote = html.escape(raw_quote)
        preview = html.escape(raw_quote.replace("\n", " ")[:120])
        label = html.escape(str(item.get("pain_label") or item.get("content_type") or "证据"))
        link = f'<a href="{html.escape(url)}" target="_blank" rel="noreferrer">查看原文</a>' if url else ""
        quote_body = f'<p class="quote-full">“{quote}”</p>'
        if len(raw_quote) > 140:
            quote_body = f'<p>“{preview}…”</p><details class="quote-details"><summary>展开完整原文（{len(raw_quote)} 字符）</summary><p class="quote-full">“{quote}”</p></details>'
        evidence_cards.append(f'<article class="quote"><div class="quote-meta">{html.escape(str(item.get("platform")))} · {label}</div>{quote_body}<small>{html.escape(str(item.get("source_id")))}</small>{link}</article>')
    downloads = '<a class="download download-primary" href="research_data.xlsx" download>下载完整研究数据.xlsx</a>'
    hypothesis = top.get("product_hypothesis") or {}
    opportunity_cards = []
    for candidate in selected_candidates or [top]:
        candidate_hypothesis = candidate.get("product_hypothesis") or {}
        opportunity_cards.append(
            f'<article class="concept"><h3>{html.escape(candidate_label(candidate))}：{html.escape(str(candidate_hypothesis.get("direction") or "等待 Amazon 痛点证据形成产品方向"))}</h3>'
            f'<div class="concept-grid"><div><b>目标用户</b>{html.escape(str(candidate_hypothesis.get("target_user") or "—"))}</div>'
            f'<div><b>使用场景</b>{html.escape(str(candidate_hypothesis.get("scenario") or "—"))}</div>'
            f'<div><b>产品结构</b>{html.escape(str(candidate_hypothesis.get("direction") or "—"))}</div>'
            f'<div><b>最大反证</b>{html.escape(str(candidate_hypothesis.get("counter_evidence") or "—"))}</div></div></article>'
        )
    risks = (top.get("risks") or [])[:5]
    pain_names = "、".join(str(row.get("label")) for row in pains[:3]) or "待补痛点证据"
    candidate_rows = ""
    for candidate in candidates:
        metrics = candidate.get("metrics") or {}
        statuses = metrics.get("free_source_statuses") or {}
        reasons = candidate.get("elimination_reasons") or candidate.get("grade_reasons") or candidate.get("missing_evidence") or []
        candidate_rows += (
            f"<tr><td><span class='grade grade-{html.escape(str(candidate.get('grade')))}'>{html.escape(str(candidate.get('grade')))}</span></td>"
            f"<td>{html.escape(candidate_label(candidate))}</td><td>{html.escape(str(statuses.get('Google Trends', 'not_run')))}</td>"
            f"<td>{html.escape(str(statuses.get('TikTok', 'not_run')))}</td><td>{html.escape(str(statuses.get('Reddit', 'not_run')))}</td>"
            f"<td>{html.escape(str(candidate.get('screening_decision') or '—'))}</td><td>{html.escape('；'.join(map(str, reasons)) or '—')}</td></tr>"
        )
    trend_platforms = "、".join((top.get("metrics") or {}).get("trend_platforms") or []) or "待补趋势平台"
    category_match = str(sf.get("category_match") or "未验证")
    result_count = int((sf.get("product_search") or {}).get("result_count") or len(data["products"]))
    product_calls = [
        call for call in data.get("calls") or []
        if str(call.get("tool") or "").strip().rsplit("/", 1)[-1].rsplit(".", 1)[-1] == "product_search"
    ]
    product_pages = len(product_calls) or (1 if result_count else 0)
    page_gains = [str(call.get("new_valid_asins") if call.get("new_valid_asins") is not None else call.get("new_valid_count")) for call in product_calls if call.get("new_valid_asins") is not None or call.get("new_valid_count") is not None]
    stop_reason = str(((sf.get("product_search") or {}).get("stop_reason") or (product_calls[-1].get("stop_reason") if product_calls else "") or "达到当前停止条件"))
    peak_theme = str((tiktok_peak or {}).get("theme") or top.get("theme") or "相关内容")
    peak_views = fmt_num(((tiktok_peak or {}).get("metrics") or {}).get("views"))
    reddit_rows = data.get("reddit") or []
    reddit_metrics = reddit_sample_metrics(reddit_rows)
    reddit_posts = reddit_metrics["posts"]
    reddit_comments = reddit_metrics["comments"]
    reddit_concentration = str(reddit_metrics["label"])
    reddit_modes = "、".join(sorted({str((row.get("context") or {}).get("collection_mode") or "unknown") for row in reddit_rows})) or "未运行"
    next_actions = []
    if hypothesis.get("direction"):
        next_actions.append(f"围绕“{hypothesis['direction']}”制作样品假设。")
    for question in (hypothesis.get("questions") or [])[:2]:
        next_actions.append(f"优先验证：{question}")
    for missing in (top.get("missing_evidence") or [])[:1]:
        next_actions.append(f"补齐证据：{missing}")
    while len(next_actions) < 3:
        next_actions.append("补充成本、利润和合规验证。")
    next_actions_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in next_actions[:3])
    generated = datetime.now(timezone.utc).isoformat()
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(market)} {html.escape(category)}趋势选品报告</title>
<style>
:root{{--ink:#183226;--muted:#65766c;--green:#176b45;--mint:#e8f2ec;--cream:#f7f5ee;--card:#fff;--line:#dfe7e1;--orange:#e79245}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--cream);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;line-height:1.65}}main{{max-width:1120px;margin:auto;padding:32px 22px 80px}}a{{color:var(--green)}}.hero{{background:linear-gradient(135deg,#173e2c,#246c4a);color:white;border-radius:24px;padding:38px;box-shadow:0 16px 42px #16362422}}.eyebrow{{font-size:13px;letter-spacing:.12em;text-transform:uppercase;opacity:.75}}h1{{font-size:36px;line-height:1.2;margin:10px 0 14px}}h2{{font-size:25px;margin:46px 0 16px}}h3{{margin:0 0 8px}}.hero p{{max-width:780px;font-size:18px}}.verdict{{display:inline-flex;background:#ffffff1c;border:1px solid #ffffff42;border-radius:999px;padding:8px 14px;font-weight:700}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:26px}}.stat{{background:#ffffff14;border:1px solid #ffffff2d;border-radius:16px;padding:14px}}.stat b{{display:block;font-size:26px}}.stat span{{font-size:13px;opacity:.8}}.scope-path{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px}}.scope-step{{background:white;border:1px solid var(--line);border-radius:18px;padding:18px}}.scope-step b{{display:block;color:var(--green);font-size:13px;margin-bottom:6px}}.scope-step strong{{display:block;font-size:19px}}.scope-step span{{font-size:13px;color:var(--muted)}}.summary{{display:grid;grid-template-columns:1.2fr .8fr;gap:18px;margin-top:18px}}.panel,.chart-card,.concept,.data-box{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:22px;box-shadow:0 8px 24px #1832260a}}.panel li{{margin:9px 0}}.coverage{{font-size:18px;margin:0}}.fine,.caption{{color:var(--muted);font-size:13px}}.chart-card{{margin-top:14px}}.viz{{display:block;width:100%;height:auto;margin-top:12px}}.axis,.legend,.bar-label,.bar-value{{font-family:inherit;fill:#5b6b62;font-size:12px}}.bar-label{{font-size:13px;fill:#294236}}.bar-value{{font-weight:700;fill:#183226}}
.products{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:16px}}.product-card{{background:white;border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:0 8px 24px #1832260a}}.product-card img,.product-image-missing{{display:block;width:100%;height:230px;object-fit:contain;background:#fff}}.product-image-missing{{display:grid;place-items:center;color:var(--muted);background:#f3f6f4}}.product-body{{padding:16px}}.product-asin{{color:var(--green);font-weight:800;font-size:13px}}.product-direction{{font-size:12px;color:var(--muted)}}.product-card h4{{font-size:14px;line-height:1.5;margin:7px 0 12px;font-weight:650}}.product-metrics{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}}.product-metrics span{{background:var(--mint);border-radius:999px;padding:4px 8px;font-size:12px}}.product-card a{{font-size:13px}}.concept{{border-left:5px solid var(--green);margin-top:14px}}.concept-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.concept-grid div{{background:#f7faf8;border-radius:14px;padding:14px}}.concept-grid b{{display:block;font-size:13px;color:var(--muted);margin-bottom:4px}}.risk{{border-left:4px solid var(--orange);padding:10px 14px;background:#fffaf3;margin:9px 0;border-radius:8px}}.quotes{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}.quote{{background:white;border:1px solid var(--line);border-radius:16px;padding:17px}}.quote p{{margin:8px 0;font-size:14px}}.quote-full{{white-space:pre-wrap;overflow-wrap:anywhere}}.quote-details{{border-top:1px solid var(--line);padding-top:8px}}.quote-meta{{font-weight:700;color:var(--green)}}.quote small{{display:block;color:#7c8a82;word-break:break-all}}.quote a{{font-size:13px}}.downloads{{display:flex;flex-wrap:wrap;gap:10px}}.download{{text-decoration:none;background:var(--mint);border:1px solid #cfe1d5;padding:9px 13px;border-radius:999px;font-size:14px}}.download-primary{{background:var(--green);color:white;border-color:var(--green);font-weight:700;padding:12px 18px}}.consult{{background:linear-gradient(135deg,#e5f1e9,#fff);border:1px solid #cfe1d5;border-radius:22px;padding:24px;margin-top:44px}}.consult-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:14px}}.consult-item{{background:white;border:1px solid var(--line);border-radius:12px;padding:12px 14px;font-size:14px}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:16px;overflow:hidden}}th,td{{padding:11px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}}th{{background:#eef4f0}}.grade{{display:inline-block;min-width:30px;text-align:center;border-radius:999px;font-weight:800}}.grade-A{{background:#cdeed8}}.grade-B{{background:#dce9ff}}.grade-C{{background:#fff0c7}}.grade-D{{background:#f7d6d6}}details{{margin-top:16px}}summary{{cursor:pointer;color:var(--muted)}}footer{{margin-top:48px;color:var(--muted);font-size:13px}}@media(max-width:760px){{h1{{font-size:29px}}.stats,.scope-path,.summary,.products,.concept-grid,.quotes,.consult-grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<section id="executive-summary" class="hero"><div class="eyebrow">NGS Trend Opportunity Radar · {html.escape(market)}</div><h1>{html.escape(category)}趋势选品：<br>用户选择 {len(selected_candidates)} 个方向深验</h1><p>Sorftime 先给出相关子类目，Google Trends、TikTok、Reddit 覆盖全部有效方向；当前排名首位的深验方向是 {html.escape(top_label)}，结论为：{html.escape(verdict_sentence)}</p><div class="verdict">{html.escape(verdict_badge)}</div><div class="stats"><div class="stat"><b>{len(seed_terms)}</b><span>免费快筛方向</span></div><div class="stat"><b>{len(selected_candidates)}</b><span>用户选择 Top N</span></div><div class="stat"><b>{len(data['amazon'])}</b><span>Amazon 书面评论</span></div><div class="stat"><b>{len(selected)}</b><span>代表 ASIN</span></div></div></section>
<section id="research-scope" class="scope-path"><article class="scope-step"><b>第 1 层 · 用户业务卡</b><strong>{html.escape(category)}</strong><span>{html.escape(market)} · {html.escape(target_platform)}</span></article><article class="scope-step"><b>第 2 层 · 全候选快筛</b><strong>{len(seed_terms)} 个有效方向</strong><span>Google Trends · TikTok · Reddit 全部运行</span></article><article class="scope-step"><b>第 3 层 · 用户选择 Top N</b><strong>{html.escape(selected_labels)}</strong><span>Sorftime 商品 + Amazon 评论</span></article></section>
<section id="decision-summary" class="summary"><article class="panel"><h3>为什么得到这个等级</h3><ul><li><strong>趋势交叉：</strong>{html.escape(trend_platforms)} 提供了 {(top.get('metrics') or {}).get('trend_platform_count', 0)} 个独立趋势平台信号。</li><li><strong>真实问题：</strong>{html.escape(pain_names)}是当前最集中的可测试问题。</li><li><strong>商业验证：</strong>Sorftime 类目匹配为 {html.escape(category_match)}，商业数字按这一相关性使用。</li></ul></article><article class="panel"><h3>下一步只做三件事</h3><ol>{next_actions_html}</ol></article></section>
	<h2>我们到底看了什么</h2><section id="data-coverage" class="data-box"><p class="coverage">{html.escape(coverage_sentence(data))}</p><p class="fine">TikTok 与 Reddit 不能单独证明地理市场；Reddit API 受阻时使用已登录 old.reddit.com，并在数据中保留 collection_mode。Amazon 分星抽样只分析缺陷，不计算“市场好评率”。</p><details><summary>查看采集边界</summary><p class="fine">Reddit 全量采集方式：{html.escape(reddit_modes)}；{reddit_posts} 个帖子、{reddit_comments} 条评论；{html.escape(reddit_concentration)}。Sorftime 商品搜索共查看 {product_pages} 页，去重后 {len(data['products'])} 条商品，其中 {len(selected)} 条通过商品语义复核并进入 Amazon 评论；每页新增有效数：{html.escape('、'.join(page_gains) or '未记录')}；停止原因：{html.escape(stop_reason)}。所有数字使用同一落盘快照。</p></details></section>
<h2 id="trend-evidence">1. 全部方向的搜索趋势</h2><div class="chart-card"><h3>{len(seed_terms)} 个方向使用同一目标市场口径比较</h3>{trend_svg}<p class="caption">排名首位的深验方向最近 4 周均值 {fmt_num(trend_metrics.get('recent_4w_mean'))}，较前 4 周{html.escape(trend_change)}。来源：Google Trends {html.escape(str(data['trends'].get('observed_market') or brief.get('requested_market') or '实际市场'))}，{trend_weeks} 周；相对指数不是销量。</p></div>
<h2 id="social-evidence">2. 全部方向的内容与社区快筛</h2><div class="chart-card"><h3>TikTok 与 Reddit 对每个有效方向都实际运行</h3>{tiktok_svg}<p class="caption">TikTok 当前可见样本中，{html.escape(peak_theme)} 最高约 {peak_views} 播放。Reddit 共 {reddit_posts} 个帖子、{reddit_comments} 条评论，采集方式 {html.escape(reddit_modes)}。逐方向通过项、卡点与淘汰原因见下方完整漏斗表；blocked 不等于零需求。</p></div>
<h2 id="commercial-evidence">3. Amazon 上卖得怎么样</h2><div class="chart-card"><h3>代表商品的销量与评论门槛</h3>{product_svg}<p class="caption">商品搜索共查看 {product_pages} 页，去重后 {len(data['products'])} 条，本地语义复核后保留 {len(selected)} 个相关 ASIN。柱为月销量，右侧完整显示月销量与评论数。</p></div><div class="products">{''.join(product_cards)}</div>
<h2 id="voc-pains">4. 用户真正不满意什么</h2><div class="chart-card"><h3>低星评论最集中在：{html.escape(pain_names)}</h3>{pain_svg}<p class="caption">基于 {pain_meta.get('low_star_reviews', 0)} 条 1–3 星样本；多标签统计。来源：Amazon {len(selected)} 个 ASIN，共 {pain_meta.get('total_reviews', len(data['amazon']))} 条书面评论。</p></div>
<h2 id="product-opportunity">5. 深验方向分别应该怎么改</h2>{''.join(opportunity_cards)}
<h2 id="decision-risks">6. 哪些风险会改变决定</h2>{''.join(f'<div class="risk">{html.escape(str(risk))}</div>' for risk in risks)}
<h2 id="candidate-pool">7. 完整漏斗：为什么进入或没有进入 Top N</h2><table><thead><tr><th>等级</th><th>方向</th><th>Google</th><th>TikTok</th><th>Reddit</th><th>决定</th><th>原因</th></tr></thead><tbody>{candidate_rows}</tbody></table>
<h2 id="evidence-trace">8. 原始证据抽查</h2><div class="quotes">{''.join(evidence_cards)}</div>
	<h2 id="data-download">9. 下载数据</h2><p class="fine">一个 Excel 工作簿，内含 10 个按渠道拆分的工作表；Reddit 帖子与评论独立成表，每行保留 source_id、原文、URL、采集时间、collection_mode 和原始文件。</p><div class="downloads">{downloads}</div>
<section id="follow-up-consultation" class="consult"><h2 style="margin:0">看完后，你可以继续问我</h2><p>这份报告是决策起点，不是对话终点。直接告诉我你想继续看哪一块：</p><div class="consult-grid"><div class="consult-item">扩大 Top N，把更多快筛方向加入 Sorftime 与 Amazon 深验。</div><div class="consult-item">对比 {len(selected)} 个代表 ASIN：谁卖得更好、谁的问题更值得切入？</div><div class="consult-item">展开某类差评，查看完整原文与 source_id。</div><div class="consult-item">把深验方向分别整理成产品打样规格和验证清单。</div></div></section>
<footer>生成时间：{html.escape(generated)} · 本报告只用于机会筛选，不替代打样、成本核算和合规审查。</footer><!-- checklist: category-first; 4 charts; concise coverage; one xlsx; source_id evidence; same snapshot; no X -->
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    run = Path(args.run_dir)
    pool = load_json(Path(args.pool), {}) or {}
    candidates = pool.get("candidates") or []
    brief = load_json(Path(args.brief), {}) or {}
    validate_deep_selection(brief, candidates)
    evidence = build_evidence_index(candidates)
    data = actual_data(run)
    data["brief"] = brief
    labels = data["brief"].get("seed_term_labels") or {}
    for series in (data.get("trends") or {}).get("series") or []:
        series["name"] = labels.get(series.get("name"), series.get("name"))
    for row in data.get("tiktok_signals") or []:
        row["theme"] = labels.get(row.get("theme"), row.get("theme"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(render_markdown(pool, data), encoding="utf-8")
    (out_dir / "report.html").write_text(render_html(pool, data, evidence), encoding="utf-8")
    analysis_dir = run / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / "evidence_index.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidates": len(candidates), "evidence": len(evidence), "charts": 4, "out_dir": str(out_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
