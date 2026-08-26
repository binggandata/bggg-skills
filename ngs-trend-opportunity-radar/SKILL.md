---
name: ngs-trend-opportunity-radar
description: Discover and validate concrete ecommerce product opportunities from a user-defined broad category using Google Trends, TikTok, Reddit, Sorftime category and Top-ASIN data, and Amazon written reviews. Use for multi-platform trend product discovery, rising product themes, community pain validation, evidence-backed product ideas, or an A/B/C/D opportunity pool with one auditable multi-sheet Excel workbook and visual HTML output. Does not procure, list, or operate stores.
---

# NGS Trend Opportunity Radar

把趋势信号一路下钻到具体 ASIN、买后缺陷和产品改良方向。Google Trends 锚定目标市场，TikTok 看内容趋势，Reddit 看独立社区讨论与使用场景，Sorftime 验证品类与代表商品，Amazon 评论验证买后问题。

## 边界

- 不采购、找供应商、上架、改店铺或替用户决定最终产品。
- 不把 Google Trends 相对指数、搜索可见样本或单条爆款当成销量或全量市场。
- 不为缺失字段补造数字；来源不支持目标市场时明确降级。
- 不采集 X；它不是本 Skill 的默认或可选数据源。
- Reddit 使用内置 `bggg-data-reddit` 模块；API 失败时正式回退到用户已登录的 `old.reddit.com`。可见 DOM 只能作为明确标记的小样本，不能冒充完整评论树。
- TikTok 语言只能证明语言匹配，不能单独证明地理市场。
- 首次调用展示 3 项业务信息（研究品类、目标市场、平台）和 1 项交付设置（输出位置）；只追问缺失项，不替用户默选。
- 首次使用若尚未连接 Sorftime，先给出配置入口 `https://open.sorftime.com/mcp`，提示用户注册并在当前 AI 工具的 MCP 设置中填写自己的 Sorftime Key，配置后只需回复“已配置”。可以说明“首次注册赠送 3 天、100 次调用”，同时注明活动以 Sorftime 页面最新规则为准。不要让用户把 Key 发到对话里，也不得把 Key 写进 Skill、报告、日志或交付包。
- 登录态是业务卡后的条件式闸门：有多个可用登录环境时必须让用户选择；不读取凭证、不静默混用账号。
- 默认只生成本地 Excel 工作簿、Markdown 与 HTML。用户确认标题、位置、收件群和机器人身份后，才读取 [`references/feishu-publishing.md`](references/feishu-publishing.md) 发布。

## 固定工作流

1. 读取 [`references/research-brief.md`](references/research-brief.md)，首次使用时先检查 Sorftime MCP，再展示并整理《趋势选品启动卡》。若 Sorftime 尚未连接，按 [`references/sorftime-budget.md`](references/sorftime-budget.md) 给出 `https://open.sorftime.com/mcp`，说明注册权益并提示用户在 MCP 设置中填写 Key；不接收明文 Key。复用用户已给信息，只追问研究品类、目标市场、平台和输出位置中的缺失项；不要追加售价、毛利、排除项或筛选范围。输出位置是交付设置，不是选品条件。
2. 业务卡齐全后，按 [`references/login-session-routing.md`](references/login-session-routing.md) 只读检查可用登录环境。只有一个时回显；多个时先让用户选择统一环境或按 Google Trends／TikTok／Reddit 浏览器回退分配，选择前不采集。
3. 回显已填写的业务卡、登录态选择，并按 [`references/source-sample-ranges.md`](references/source-sample-ranges.md) 展示每个平台的固定采集范围、Reddit API→old Reddit 回退路线、实际覆盖风险和 Sorftime 预算；用户确认后才开始外部采集或付费调用。
4. 从用户的大品类生成 5～10 个互不重复的商品子方向。Google Trends 必做：按目标国家和当地常用语言比较这些商品词，形成候选排序。再按 [`references/source-routing.md`](references/source-routing.md) 用 TikTok 与 Reddit 补证并检查查询语义。TikTok 使用内置 `bggg-data-tiktok`，Reddit 使用内置 `bggg-data-reddit`；分别读取 [`references/bggg-data-tiktok.md`](references/bggg-data-tiktok.md) 与 [`references/bggg-data-reddit.md`](references/bggg-data-reddit.md)，不要求用户另行安装。
5. 按 [`references/source-sample-ranges.md`](references/source-sample-ranges.md) 和 [`references/sample-gates.md`](references/sample-gates.md) 分两级采样。Top 5 做快速筛选；Top 1～3 达到独立父内容和有效文本门槛后才能进入深挖。评论型平台的最终 Top 1 均不得少于 100 条有效评论。
6. 默认只深挖 Top 1：Sorftime 先用 `category_search_from_product_name` 验证品类，再用 `product_search` 取第一页 20 个商品。人工检查语义；若不足 3 个字段完整的相关代表 ASIN，按 [`references/degradation-and-pagination.md`](references/degradation-and-pagination.md) 自动翻页，默认最多看 3 页（含第一页），拿到 3～10 个后提前停止。第 3 页仍不足时先汇报每页新增有效数，再问用户是否继续以及是否调整最大翻页上限。不逐个调用 `product_detail`。
7. 为代表 ASIN 创建 `config/amazon_targets.tsv`，用 `bggg-data-amazon` 抓 Amazon US 书面评论。优先 1 个核心 ASIN 用 `full`，其余用 `basic`；分星抽样不能用来计算市场好评率。
8. 从 Amazon 低星缺陷、TikTok 评论和达到独立父帖门槛的 Reddit 讨论生成可解决的产品假设；每个结论都保留 `source_id`、原文、URL、父级 ID 与 `collection_mode`。
9. 按 [`references/opportunity-grading.md`](references/opportunity-grading.md) 分为 A／B／C／D；缺少 Amazon 买后验证的候选不能成为最终 A 级产品机会。
10. 运行确定性脚本统计，先生成按渠道区分的内部 CSV，再合并为一个 `research_data.xlsx`；同时生成 Markdown 与可视化 HTML。代表 ASIN 同时展示产品图和关键指标，长证据原文可展开完整查看。数据文件契约见 [`references/report-contract.md`](references/report-contract.md)，主报告固定模板见 [`references/report-template.md`](references/report-template.md)，交付前执行 [`references/quality-checklist.md`](references/quality-checklist.md)。
11. 报告交付后主动给出 3～5 个可继续咨询的方向，例如 ASIN 对比、完整差评证据、产品打样规格或换市场重跑；等待用户选择，不自动扩展研究或发布。

## 脚本

从本 Skill 根目录运行：

```bash
python3 scripts/bggg_data_tiktok_plan.py --queries '<run>/config/tiktok_queries.tsv' --output '<run>/work/tiktok/request_plan.json'
python3 scripts/bggg_data_tiktok.py search --query '<local product term>' --requested-market '<market>' --language '<language>' --output '<run>/data/raw/tiktok_<date>.jsonl' --screenshot-dir '<run>/quality/tiktok-screenshots'
python3 scripts/bggg_data_tiktok.py comments --video-url '<url1>' '<url2>' '<url3>' --requested-market '<market>' --language '<language>' --output '<run>/data/raw/tiktok_<date>.jsonl' --screenshot-dir '<run>/quality/tiktok-screenshots' --append
python3 scripts/bggg_data_tiktok_normalize.py --inputs '<run>/work/tiktok/source_json/*.json' --output '<run>/data/raw/tiktok_<date>.jsonl' --summary '<run>/work/tiktok/normalize_summary.json' --keywords '<run>/config/keywords.txt'
python3 scripts/analyze_tiktok_samples.py --inputs '<run>/data/raw/tiktok_*.jsonl' --relevance '<run>/config/tiktok_relevance.tsv' --output '<run>/analysis/tiktok_sample_gates.json'
python3 scripts/bggg_data_reddit_plan.py --queries '<run>/config/reddit_queries.tsv' --output '<run>/work/reddit/request_plan.json' --raw-dir '<run>/data/raw/source_json' --requested-market '<market>'
python3 scripts/bggg_data_reddit_api.py search --plan '<run>/work/reddit/request_plan.json' --manifest '<run>/work/reddit/source_manifest.jsonl' --failure-log '<run>/work/reddit/failure_log.jsonl' --summary '<run>/work/reddit/api_search_summary.json' --max-pages 1
python3 scripts/bggg_data_reddit_api.py comments --targets '<run>/config/reddit_posts.tsv' --raw-dir '<run>/data/raw/source_json' --requested-market '<market>' --manifest '<run>/work/reddit/source_manifest.jsonl' --failure-log '<run>/work/reddit/failure_log.jsonl' --summary '<run>/work/reddit/api_comments_summary.json'
python3 scripts/bggg_data_reddit_normalize.py --manifest '<run>/work/reddit/source_manifest.jsonl' --output '<run>/data/raw/reddit_<lang>_<date>.jsonl' --summary '<run>/work/reddit/normalize_summary.json' --keywords '<run>/config/keywords.txt'
python3 scripts/bggg_data_reddit_visible_normalize.py --inputs '<run>/work/reddit/visible_dom/*.json' --output '<run>/data/raw/reddit_visible_<lang>_<date>.jsonl' --summary '<run>/work/reddit/visible_dom_summary.json' --keywords '<run>/config/keywords.txt' --requested-market '<market>'
python3 scripts/analyze_reddit_samples.py --inputs '<run>/data/raw/reddit*.jsonl' --relevance '<run>/config/reddit_relevance.tsv' --output '<run>/analysis/reddit_sample_gates.json'
python3 scripts/normalize_signals.py --inputs '<run>/data/signals/*.jsonl' --output '<run>/analysis/themes.json'
python3 scripts/analyze_review_pains.py --input '<run>/data/raw/amazon_woot_<date>.jsonl' --taxonomy '<run>/config/pain_taxonomy.json' --output '<run>/analysis/amazon_pain_stats.json'
python3 scripts/export_audit_csv.py --run-dir '<run>'
# 按 Spreadsheets Skill 提供的 Node 运行时和 @oai/artifact-tool 环境执行：
node scripts/build_research_workbook.mjs --run-dir '<run>'
python3 scripts/rank_candidates.py --input '<run>/analysis/candidates.json' --output '<run>/analysis/opportunity_pool.json'
python3 scripts/render_report.py --brief '<run>/00-research-brief/research_brief.json' --pool '<run>/analysis/opportunity_pool.json' --run-dir '<run>' --out-dir '<run>/report'
python3 scripts/validate_run.py --run-dir '<run>' --soft-call-cap 2 --hard-call-cap 5
```

内置 `bggg-data-tiktok` 负责 TikTok 可见页面采集；内置 `bggg-data-reddit` 负责 Reddit API、`old.reddit.com` 回退与规范化；其余脚本负责去重、门槛判断、渲染和证据检查。查询语义／语言复核、痛点可解决性、产品假设与最终进入决策由 Agent 和用户完成。

## 默认调用额度

- Top 1 正常下钻共 2 次：一次品类搜索、一次商品搜索；若第一页语义相关代表商品不足，最多自动翻到第 3 页，最坏 4 次调用。
- 若用户要求比较 Top 3 品类，可先各做一次品类搜索，再只对胜出的 Top 1 追加一次商品搜索，总计 4 次。
- 默认最大翻页上限 3 页（包含第一页）；第 3 页后继续或修改上限都必须先获得用户确认。
- 硬上限 5 次；超过 5 次必须先获得用户确认。
- 默认不调用 `product_detail`、Sorftime `product_reviews` 或 `category_report`；Amazon 评论走 `bggg-data-amazon`。

## 最终交付

面向用户只交付 3 个文件：

1. `report/report.html`：主报告，按固定模板展示研究范围、结论、4～5 张图、代表 ASIN 产品卡、真实痛点、产品机会、风险、证据与继续咨询入口。
2. `report/research_data.xlsx`：唯一正式数据文件，含 10 个按渠道拆分的工作表，Reddit 帖子和评论独立成表。
3. `report/report.md`：方便复制、归档或确认后发布飞书的轻量文字版。

运行目录同时保留审计材料，但不作为用户必须逐个打开的交付：原始 JSON／JSONL、内部 CSV、Sorftime 调用日志、证据索引、痛点统计、A／B／C／D 机会池、截图、工作簿预览、失败日志和 `quality/validation.json`。

最终回复先给一句话结论和 3 个文件路径，再用人话说明实际覆盖、关键缺口与 Sorftime 调用次数。报告末尾提供 3～5 个“可以继续问我什么”，等待用户选择，不自动扩展研究。

## 默认开场

> 开始前先确认一张启动卡：
>
> 【趋势选品启动卡】<br/>
> 1. 研究品类：<br/>
> 2. 目标市场：<br/>
> 3. 平台：<br/>
> 4. 输出位置：
>
> 也可以直接回复：“家居收纳｜美国｜Amazon｜桌面/趋势选品报告”。我会回显业务信息、交付位置和调用预算，确认后再采集。
>
> 第一次使用且尚未连接 Sorftime：打开 https://open.sorftime.com/mcp 注册并按页面说明配置 MCP。首次注册赠送 3 天、100 次调用，具体活动以页面最新规则为准。请把 Key 填在当前 AI 工具的 MCP 设置中，不要发到对话里；配置后只需回复“已配置”。已经连接则跳过。
