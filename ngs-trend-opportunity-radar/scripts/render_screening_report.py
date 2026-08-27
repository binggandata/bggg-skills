#!/usr/bin/env python3
"""Render the all-direction screening checkpoint before the user selects Top N."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


PALETTE = ["#176b45", "#e79245", "#4267a8", "#9a5ea8", "#d15b5b", "#648a70", "#b7791f", "#0f766e"]


def load_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fmt_int(value) -> str:
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return "—"


def fmt_pct(value, digits=1) -> str:
    try:
        return f"{float(value):+.{digits}%}"
    except (TypeError, ValueError):
        return "—"


def svg_bars(rows: list[tuple[str, float | None, str]], title: str, color: str = "#176b45") -> str:
    valid = [value for _, value, _ in rows if value is not None]
    maximum = max(valid, default=1) or 1
    width, left, bar_x, right = 960, 22, 260, 925
    row_h, top = 48, 48
    height = top + row_h * len(rows) + 28
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">']
    for idx, (label, value, note) in enumerate(rows):
        y = top + idx * row_h
        out.append(f'<text x="{left}" y="{y + 17}" class="bar-label">{html.escape(label)}</text>')
        out.append(f'<rect x="{bar_x}" y="{y}" width="{right-bar_x}" height="22" rx="11" fill="#e7eee9"/>')
        if value is not None:
            bar_w = (right - bar_x) * max(0, value) / maximum
            out.append(f'<rect x="{bar_x}" y="{y}" width="{bar_w:.1f}" height="22" rx="11" fill="{color}"/>')
        out.append(f'<text x="{right}" y="{y + 17}" text-anchor="end" class="bar-value">{html.escape(note)}</text>')
    return "".join(out) + "</svg>"


def svg_grouped_percent(rows: list[tuple[str, float | None, float | None]], title: str) -> str:
    width, height = 960, 420
    left, top, plot_w, plot_h = 80, 45, 840, 280
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">']
    for tick in range(0, 101, 25):
        y = top + plot_h - tick / 100 * plot_h
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#dfe7e1"/>')
        out.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" class="axis">{tick}%</text>')
    group_w = plot_w / max(1, len(rows))
    for idx, (label, amazon, low_reviews) in enumerate(rows):
        base_x = left + idx * group_w + group_w * 0.2
        for offset, value, color in ((0, amazon, "#d15b5b"), (group_w * 0.28, low_reviews, "#176b45")):
            if value is None:
                continue
            h = max(0, min(100, value)) / 100 * plot_h
            out.append(f'<rect x="{base_x+offset:.1f}" y="{top+plot_h-h:.1f}" width="{group_w*0.22:.1f}" height="{h:.1f}" rx="4" fill="{color}"/>')
        out.append(f'<text x="{left+(idx+0.5)*group_w:.1f}" y="{top+plot_h+22}" text-anchor="middle" class="axis">{html.escape(label[:8])}</text>')
    out.append('<circle cx="235" cy="380" r="6" fill="#d15b5b"/><text x="248" y="385" class="legend">Amazon 自营销量占比</text>')
    out.append('<circle cx="500" cy="380" r="6" fill="#176b45"/><text x="513" y="385" class="legend">低于 300 评论商品销量占比</text>')
    return "".join(out) + "</svg>"


def svg_lines(series: list[dict], title: str) -> str:
    width, height = 960, 390
    left, top, plot_w, plot_h = 58, 42, 850, 250
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">']
    for tick in range(0, 101, 25):
        y = top + plot_h - tick / 100 * plot_h
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#dfe7e1"/>')
        out.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" class="axis">{tick}</text>')
    for idx, item in enumerate(series):
        values = item.get("values") or []
        if not values:
            continue
        points = []
        for pos, value in enumerate(values):
            x = left + pos / max(1, len(values)-1) * plot_w
            y = top + plot_h - max(0, min(100, float(value))) / 100 * plot_h
            points.append(f"{x:.1f},{y:.1f}")
        out.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{PALETTE[idx % len(PALETTE)]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
    for idx, item in enumerate(series):
        x = 65 + (idx % 4) * 215
        y = 340 + (idx // 4) * 24
        out.append(f'<circle cx="{x}" cy="{y-4}" r="5" fill="{PALETTE[idx % len(PALETTE)]}"/><text x="{x+12}" y="{y}" class="legend">{html.escape(item["name"])}</text>')
    return "".join(out) + "</svg>"


def trend_series(run: Path, directions: list[dict]) -> dict[str, list[dict]]:
    names = {row["candidate_id"]: row["name"] for row in directions}
    points = defaultdict(list)
    for row in load_jsonl(run / "data" / "signals" / "google_trends_product_terms.jsonl"):
        context = row.get("context") or {}
        if context.get("window") != "12m" or row.get("observed_market") != "US":
            continue
        date = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", str(row.get("text_raw") or ""))
        points[row.get("theme")].append((date.group(1) if date else "", row.get("value") or 0))
    grouped = {"home": [], "pet": []}
    for candidate_id, rows in points.items():
        values = [value for _, value in sorted(rows)]
        grouped["home" if candidate_id.startswith("home_") else "pet"].append({"name": names.get(candidate_id, candidate_id), "values": values})
    return grouped


def evidence_rows(run: Path, directions: list[dict]) -> list[dict]:
    samples = []
    for platform, path in (
        ("TikTok", run / "data" / "clean" / "tiktok_screening.jsonl"),
        ("Reddit", run / "data" / "clean" / "reddit_screening.jsonl"),
    ):
        by_candidate = defaultdict(list)
        for row in load_jsonl(path):
            by_candidate[(row.get("context") or {}).get("candidate_id")].append(row)
        for direction in directions:
            rows = by_candidate.get(direction["candidate_id"]) or []
            if not rows:
                continue
            row = rows[0]
            context = row.get("context") or {}
            samples.append({
                "candidate_id": direction["candidate_id"], "theme": direction["name"],
                "source_id": row.get("source_id"), "platform": platform,
                "content_type": row.get("content_type") or context.get("content_type"),
                "url": context.get("url") or context.get("source_url"),
                "text_raw": row.get("text_raw") or "", "collection_mode": context.get("collection_mode"),
            })
    return samples


def render_markdown(funnel: dict, evidence: list[dict]) -> str:
    directions = funnel.get("directions") or []
    recommended = [row for row in directions if row.get("decision") == "建议深验"]
    lines = [
        "# 家居收纳＋宠物清洁：8 个方向快筛报告", "",
        "> 当前已完成所有候选方向的统一快筛，尚未选择 Top N。Amazon 商品评论深验未运行，不是抓取失败。", "",
        "## 先说结论", "",
        "建议优先进入深验的 4 个方向：**浴室收纳、衣物与衣橱收纳、狗狗美容清洁用品、猫咪美容清洁用品**。", "",
        "- 浴室收纳：规模成立、Amazon 自营占比较低，跨平台场景信号完整。",
        "- 衣物与衣橱收纳：规模最大、TikTok 表现最强，但成熟度高，要靠差评找结构突破。",
        "- 狗狗美容清洁：长期搜索增长明显，内容商品化较强，但新卖家进入门槛需要深验。",
        "- 猫咪美容清洁：增长来自小基数，适合小规模验证，不适合先压重库存。", "",
        "## 一共抓到了什么", "",
        "| 数据源 | 本轮数据 |", "|---|---|",
        "| Sorftime | 10 次类目树调用＋8 次候选市场报告；8 个方向全部有商业快照 |",
        "| Google Trends | 3,780 个周度数据点；美国／加拿大、近 12 个月／近 5 年 |",
        "| TikTok | 96 个相关视频；8 个方向各 12 条，使用登录态 Chrome |",
        "| Reddit | 331 篇严格语义清洗帖子；8 个方向均超过 10 篇 |",
        "| Amazon | 0 条评论；等待用户选择 Top N 后再抓，不属于数据缺失 |", "",
        "## 8 个方向为什么留或不留", "",
        "| 方向 | Top100月销量 | 最近一年同比* | TikTok | Reddit | 当前建议 | 原因 |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for row in directions:
        lines.append(
            f"| {row['name']} | {fmt_int((row.get('sorftime') or {}).get('top100_monthly_sales_volume'))} | "
            f"{fmt_pct((row.get('google_trends') or {}).get('us_5y_recent_year_vs_prior'))} | "
            f"{(row.get('tiktok') or {}).get('videos', 0)} 条 | {(row.get('reddit') or {}).get('posts', 0)} 篇 | "
            f"{row.get('decision')} | {'；'.join(row.get('reasons') or [])} |"
        )
    lines += ["", "\\* 最近一年同比指五年序列中最近 52 周均值对比此前 52 周，不是五年累计增长。", "",
              "## 下一步", "", f"请从建议方向中选择 Top N。目前建议池共 {len(recommended)} 个方向。选择后才会调用 Sorftime 商品搜索并抓 Amazon 书面评论。", "",
              "## 数据文件", "", "- [下载完整研究数据工作簿](research_data.xlsx)", "", "## 证据抽查", ""]
    for row in evidence[:16]:
        text = str(row.get("text_raw") or "").replace("\n", " ")
        if len(text) > 180:
            text = text[:177] + "…"
        link = row.get("url") or ""
        suffix = f" · [原始链接]({link})" if link.startswith("http") else ""
        lines.append(f"- {row.get('theme')} · {row.get('platform')} · `{row.get('source_id')}` · {text}{suffix}")
    lines += ["", "## 免责声明", "", "本报告用于缩小研究范围，不替代打样、成本核算、专利与合规审查。Google Trends 是相对指数；TikTok 与 Reddit 只能证明内容或社区语境，不能单独证明发布者来自目标市场。具体结论应结合你的供应链、售价和风险承受能力调整。", ""]
    return "\n".join(lines)


def render_html(funnel: dict, grouped_trends: dict[str, list[dict]], evidence: list[dict]) -> str:
    directions = funnel.get("directions") or []
    recommended = [row for row in directions if row.get("decision") == "建议深验"]
    sales_rows = [(row["name"], (row.get("sorftime") or {}).get("top100_monthly_sales_volume"), fmt_int((row.get("sorftime") or {}).get("top100_monthly_sales_volume"))) for row in directions]
    tiktok_rows = [(row["name"], (row.get("tiktok") or {}).get("visible_metric_median"), fmt_int((row.get("tiktok") or {}).get("visible_metric_median"))) for row in directions]
    reddit_rows = [(row["name"], (row.get("reddit") or {}).get("posts"), f"{fmt_int((row.get('reddit') or {}).get('posts'))} 篇") for row in directions]
    competition_rows = [(row["name"], (row.get("sorftime") or {}).get("amazon_owned_share_pct"), (row.get("sorftime") or {}).get("low_review_sales_share_pct")) for row in directions]
    table_rows = []
    for row in directions:
        decision_class = "go" if row.get("decision") == "建议深验" else "narrow" if "收窄" in str(row.get("decision")) else "watch"
        table_rows.append(
            f'<tr><td><strong>{html.escape(row["name"])}</strong></td><td>{fmt_int((row.get("sorftime") or {}).get("top100_monthly_sales_volume"))}</td>'
            f'<td>{fmt_pct((row.get("google_trends") or {}).get("us_5y_recent_year_vs_prior"))}</td>'
            f'<td>{(row.get("tiktok") or {}).get("videos", 0)} 条 / {(row.get("tiktok") or {}).get("authors", 0)} 作者</td>'
            f'<td>{(row.get("reddit") or {}).get("posts", 0)} 篇</td><td><span class="pill {decision_class}">{html.escape(str(row.get("decision")))}</span></td>'
            f'<td>{html.escape("；".join(row.get("reasons") or []))}</td></tr>'
        )
    evidence_cards = []
    for row in evidence[:16]:
        source_text = html.escape(str(row.get("text_raw") or ""))
        url = str(row.get("url") or "")
        link = f'<a href="{html.escape(url)}" target="_blank" rel="noopener">打开原始页面</a>' if url.startswith("http") else ""
        evidence_cards.append(f'<article class="quote"><div class="quote-head">{html.escape(str(row.get("theme")))} · {html.escape(str(row.get("platform")))}</div><p>{source_text}</p><small>source_id：{html.escape(str(row.get("source_id")))}</small>{link}</article>')
    recommended_cards = []
    for row in recommended:
        recommended_cards.append(f'<article class="pick"><div class="pick-no">TOP 候选</div><h3>{html.escape(row["name"])}</h3><p>{html.escape("；".join(row.get("reasons") or []))}</p></article>')
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>家居收纳＋宠物清洁｜8 个方向快筛报告</title><style>
:root{{--ink:#17251e;--muted:#65736b;--green:#176b45;--green2:#2d7a59;--mint:#e9f3ed;--cream:#f7f4ec;--card:#fff;--orange:#e79245;--red:#bd4b4b;--line:#dce5df}}*{{box-sizing:border-box}}body{{margin:0;background:var(--cream);color:var(--ink);font:15px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}main{{max-width:1160px;margin:auto;padding:32px 24px 72px}}.hero{{background:linear-gradient(135deg,#144c36,#1f7650);color:white;border-radius:28px;padding:42px;box-shadow:0 18px 50px #174b3424}}.eyebrow{{font-size:13px;letter-spacing:.12em;opacity:.78}}h1{{font-size:42px;line-height:1.18;margin:12px 0 14px}}.hero p{{max-width:820px;font-size:17px;color:#e8f4ec}}.status{{display:inline-block;background:#ffe8bc;color:#70420b;border-radius:999px;padding:8px 14px;font-weight:800}}.stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:28px}}.stat{{background:#ffffff15;border:1px solid #ffffff30;border-radius:16px;padding:15px}}.stat b{{font-size:26px;display:block}}.stat span{{font-size:12px;color:#d5e9dc}}h2{{font-size:27px;margin:48px 0 16px}}h3{{margin:0 0 8px}}.stage{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:20px}}.step{{background:white;border:1px solid var(--line);border-radius:18px;padding:18px}}.step b{{display:block;color:var(--green);font-size:12px}}.step strong{{display:block;margin:6px 0}}.step.pending{{border-style:dashed;background:#fffaf0}}.summary{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}.panel,.chart-card,.data-box{{background:white;border:1px solid var(--line);border-radius:20px;padding:22px}}.picks{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}.pick{{background:white;border:1px solid #cde0d3;border-left:5px solid var(--green);border-radius:18px;padding:18px}}.pick-no{{color:var(--green);font-size:12px;font-weight:800}}.coverage{{font-size:18px;font-weight:650}}.fine,.caption{{color:var(--muted);font-size:13px}}.chart{{width:100%;height:auto}}.bar-label{{font-size:13px;fill:#31463a}}.bar-value{{font-size:12px;font-weight:700;fill:#31463a}}.axis,.legend{{font-size:12px;fill:#68766e}}.chart-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}table{{width:100%;border-collapse:separate;border-spacing:0;background:white;border:1px solid var(--line);border-radius:18px;overflow:hidden}}th,td{{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{background:#edf4ef;color:#375246;font-size:13px}}td{{font-size:13px}}tr:last-child td{{border-bottom:0}}.pill{{display:inline-block;border-radius:999px;padding:3px 9px;font-weight:700;white-space:nowrap}}.go{{background:#cfead8;color:#165d3c}}.watch{{background:#fff0c9;color:#75520d}}.narrow{{background:#f8dada;color:#8a3333}}.quotes{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.quote{{background:white;border:1px solid var(--line);border-radius:16px;padding:16px}}.quote-head{{font-weight:800;color:var(--green)}}.quote p{{white-space:pre-wrap;max-height:190px;overflow:auto;font-size:13px}}.quote small{{display:block;color:#78867e;word-break:break-all}}.quote a{{display:inline-block;margin-top:8px;color:var(--green)}}.download{{display:inline-block;background:var(--green);color:white;text-decoration:none;border-radius:999px;padding:12px 18px;font-weight:800}}.next{{background:linear-gradient(135deg,#e6f2ea,#fff);border:1px solid #cde0d3;border-radius:22px;padding:24px}}details{{margin-top:14px}}summary{{cursor:pointer;color:var(--muted)}}footer{{margin-top:46px;color:var(--muted);font-size:13px}}@media(max-width:820px){{h1{{font-size:30px}}.stats,.stage,.summary,.picks,.chart-grid,.quotes{{grid-template-columns:1fr}}.hero{{padding:28px}}table{{display:block;overflow-x:auto}}}}
</style></head><body><main>
<section id="executive-summary" class="hero"><div class="eyebrow">NGS TREND OPPORTUNITY RADAR · 快筛阶段</div><h1>家居收纳＋宠物清洁<br>8 个方向统一快筛</h1><p>不是“随便挑一个产品”。候选来自 Sorftime 官方类目树，8 个方向全部跑完 Google Trends、TikTok、Reddit 和 Sorftime 市场快照，再给出保留、观察或收窄建议。</p><span class="status">等待你选择 Top N，Amazon 深验尚未运行</span><div class="stats"><div class="stat"><b>8</b><span>完整快筛方向</span></div><div class="stat"><b>3,780</b><span>Google 周度点</span></div><div class="stat"><b>96</b><span>TikTok 视频</span></div><div class="stat"><b>331</b><span>Reddit 帖子</span></div><div class="stat"><b>18</b><span>Sorftime 调用</span></div></div></section>
<section id="research-scope" class="stage"><article class="step"><b>1 · 用户研究品类</b><strong>家居收纳、宠物清洁</strong><span>目标以 Amazon 北美市场为主</span></article><article class="step"><b>2 · 官方类目树</b><strong>每个品类 5 次展开</strong><span>候选来自 Sorftime 节点，不由模型随便拆</span></article><article class="step"><b>3 · 全方向快筛</b><strong>8 个方向全部跑完</strong><span>Google · TikTok · Reddit · Sorftime</span></article><article class="step pending"><b>4 · 用户选择 Top N</b><strong>尚未选择</strong><span>选择后才跑商品池和 Amazon 评论</span></article></section>
<h2 id="decision-summary">先说结论</h2><div class="summary"><article class="panel"><h3>建议优先深验 4 个方向</h3><p>浴室收纳、衣物与衣橱收纳、狗狗美容清洁用品、猫咪美容清洁用品。</p><p class="fine">这不是最终选品结论，而是从 8 个方向里筛出的下一轮候选池。</p></article><article class="panel"><h3>三个重要判断</h3><ul><li>厨房收纳规模最大，但父类目语义过宽，应先收窄。</li><li>猫砂类目很大，但 Amazon 自营占比高，应优先看配件。</li><li>多数方向最近 13 周在降温，不能写成“现在全面爆发”。</li></ul></article></div>
<div class="picks">{''.join(recommended_cards)}</div>
<h2 id="data-coverage">一共抓到了什么</h2><section class="data-box"><p class="coverage">Sorftime 10 次类目树＋8 次市场报告；Google Trends 3,780 个周度点；TikTok 96 个视频；Reddit 331 篇帖子。Amazon 0 条评论，因为尚未选择 Top N，不是抓取失败。</p><details><summary>查看口径边界</summary><p class="fine">Google Trends 是同组关键词内的相对指数，不是销量。TikTok 使用用户登录态 Chrome，语言匹配不能单独证明发布者来自北美。Reddit 使用登录态 old Reddit 同源数据，帖子用于快筛；评论树只在深验阶段采集。Sorftime 类目报告用于市场结构，product_search 尚未调用。</p></details></section>
<h2 id="commercial-evidence">1. 哪些方向有足够市场规模</h2><section class="chart-card"><h3>8 个方向 Sorftime Top-100 月销量</h3>{svg_bars(sales_rows, 'Sorftime Top-100 monthly sales', '#176b45')}<p class="caption">来源：Sorftime category_report，n=8 个候选方向。厨房收纳和猫砂方向的父类目口径偏宽，规模不能直接等同于具体产品机会。</p></section>
<h2 id="trend-evidence">2. 搜索需求怎么变化</h2><div class="chart-grid"><section class="chart-card"><h3>家居收纳：美国近 12 个月</h3>{svg_lines(grouped_trends.get('home') or [], 'Home organization Google Trends US 12m')}<p class="caption">同一组关键词内相对指数。长期增长不代表最近一季仍在加速。</p></section><section class="chart-card"><h3>宠物清洁：美国近 12 个月</h3>{svg_lines(grouped_trends.get('pet') or [], 'Pet cleaning Google Trends US 12m')}<p class="caption">猫咪美容的同比增幅来自极小基数，必须结合绝对指数判断。</p></section></div>
<h2 id="social-evidence">3. TikTok 和 Reddit 有没有真实内容</h2><div class="chart-grid"><section class="chart-card"><h3>TikTok：每个方向 12 条视频</h3>{svg_bars(tiktok_rows, 'TikTok median visible metric', '#e79245')}<p class="caption">横条为可见指标中位数；猫咪美容部分页面未稳定暴露互动字段，因此保留缺失，不补零。</p></section><section class="chart-card"><h3>Reddit：8 个方向均超过 10 篇</h3>{svg_bars(reddit_rows, 'Reddit relevant posts', '#4267a8')}<p class="caption">严格语义清洗后共 331 篇父帖；本阶段用于判断讨论存在性和场景，不把帖子评论数当成已抓评论。</p></section></div>
<h2>4. 竞争结构会不会卡住进入</h2><section class="chart-card"><h3>Amazon 自营占比越高越难正面进入；低评论商品占比越高越有新人窗口</h3>{svg_grouped_percent(competition_rows, 'Amazon owned share and low-review sales share')}<p class="caption">来源：Sorftime category_report。猫砂与如厕清洁 Amazon 自营占比约 80%，厨房收纳约 53%；浴室收纳仅约 1%。</p></section>
<h2 id="candidate-pool">5. 8 个方向为什么留、为什么不留</h2><table><thead><tr><th>方向</th><th>Top100月销量</th><th>最近一年同比*</th><th>TikTok</th><th>Reddit</th><th>建议</th><th>原因</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table><p class="fine">* 最近一年同比：五年序列中最近 52 周均值对比此前 52 周，不是五年累计增长。</p>
<h2 id="voc-pains">6. Amazon 差评为什么没有</h2><section class="data-box"><h3>这是工作流阶段，不是平台数据失败</h3><p>本轮只完成“全方向快筛”。你选择 Top N 后，Skill 才会对所选方向调用 Sorftime 商品搜索，筛 3–10 个相关 ASIN，并抓每个方向至少 100 条 Amazon 书面评论。现在提前抓，会把预算花在你可能不想深验的方向上。</p></section>
<h2 id="evidence-trace">7. 原始证据抽查</h2><div class="quotes">{''.join(evidence_cards)}</div>
<h2 id="data-download">8. 下载数据</h2><p>正式数据只提供一个工作簿，10 个渠道工作表分别保存原始数据和“未运行”的阶段说明。</p><a class="download" href="research_data.xlsx" download>下载 research_data.xlsx</a>
<section id="follow-up-consultation" class="next"><h2 style="margin:0">下一步由你选择</h2><p>你可以回复：“深验 2 个：浴室收纳、狗狗美容清洁”，或者让我把 4 个建议方向全部深验。选择后我会先告诉你 Sorftime 最少／最多新增调用次数，再继续抓商品和 Amazon 评论。</p></section>
<footer>生成时间：{html.escape(generated)} · 本报告用于机会筛选，不替代打样、成本、专利和合规审查。结论需结合你的业务条件调整。</footer>
</main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    run = Path(args.run_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    funnel = load_json(run / "analysis" / "screening_funnel.json", {}) or {}
    if funnel.get("stage") != "all_direction_screening_complete_waiting_for_user_top_n":
        raise SystemExit("screening_funnel.json is missing or not at the waiting-for-Top-N stage")
    evidence = evidence_rows(run, funnel.get("directions") or [])
    (run / "analysis" / "evidence_index.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "report.md").write_text(render_markdown(funnel, evidence), encoding="utf-8")
    (out / "report.html").write_text(render_html(funnel, trend_series(run, funnel.get("directions") or []), evidence), encoding="utf-8")
    print(json.dumps({"stage": funnel.get("stage"), "directions": len(funnel.get("directions") or []), "evidence": len(evidence), "charts": 6, "out_dir": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
