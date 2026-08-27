---
name: ngs-trend-opportunity-radar
description: Discover and validate concrete ecommerce product opportunities from a user-defined starting research category using Google Trends, TikTok, Reddit, Sorftime category and Top-ASIN data, and Amazon written reviews. Use for multi-platform trend product discovery, rising product themes, community pain validation, evidence-backed product ideas, or an A/B/C/D opportunity pool with one auditable multi-sheet Excel workbook and visual HTML output. Does not procure, list, or operate stores.
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
3. 回显业务卡、登录态选择、三个免费源的固定快筛范围，以及 Sorftime 的候选发现调用预算；用户确认后才开始外部采集或付费调用。
4. 先判断研究品类能否直接查询：`家居收纳`、`宠物清洁`这类业务品类可直接进入候选发现；`Home & Kitchen` 这类平台一级大类需先收窄，已具体到单一商品或 SKU 则跳过候选漏斗，改走单品验证。不得由模型先凭经验拆出固定数量的方向。随后调用一次 Sorftime `category_search_from_product_name`，用用户的研究品类和目标站点取得相关子类目、Node ID 与市场规模。若只返回 0～1 个有效子类目，标记 `sparse`，不能直接建立 Top 漏斗；按预算规则说明后再用 `category_tree` 定位正式父节点或子节点。
5. 从 Sorftime 返回中保留全部语义相关、可对应具体商品的子类目，再经过去重和粒度统一形成“候选方向”；不预设候选数量，也不把模型自行联想的产品混入候选池。每个候选方向必须可搜索、互不重复，并保存 `source_category_node_ids`、来源子类目、本地语言名称、跨平台搜索词、纳入理由和市场规模。重复、抽象需求、品牌词、非商品节点或语义偏题项进入 `excluded_directions`，记录排除原因。不同父节点查询若返回相同结果，或大部分行不属于目标分支，整次结果标记 `semantic_mismatch`，不得进入候选池。只有 `category_discovery_status=ready` 才能进入三源快筛。
6. 按 [`references/source-sample-ranges.md`](references/source-sample-ranges.md) 和 [`references/sample-gates.md`](references/sample-gates.md) 对每个候选方向统一运行三个免费源：Google Trends 看搜索需求，TikTok 看内容扩散与使用演示，Reddit 看社区讨论与真实场景。跨平台比较单位是“候选方向”，不是要求各平台存在同名类目。任何方向都不得因早期排名而跳过某一免费源。每个“找不到”必须区分 `blocked`、`empty`、`semantic_mismatch` 和真实弱信号；前两类不能写成零需求。
7. 免费快筛完成后先交付漏斗表：每个方向的三个来源状态、关键数字、通过项、卡点、初步等级、保留／淘汰决定及理由。此时停止，询问用户希望多少个方向进入深验；Top N 必须由用户明确选择，不默认为 Top 1。
8. 用户选择 Top N 后，按 [`references/sorftime-budget.md`](references/sorftime-budget.md) 计算最少与最坏调用数并确认预算。对所选方向复用候选发现阶段的类目规模；只有映射缺失或偏题时才追加类目校正。随后分别调用 `product_search` 取代表商品，语义筛选后每方向保留 3～10 个 ASIN。每方向默认最多看 3 页，达到 3～10 个即停止；第 4 页前再次确认。
9. 为每个深验方向分别创建 Amazon 目标，使用 `bggg-data-amazon` 抓 Amazon US 书面评论；每方向至少 100 条，正常目标 300～1000 条。优先 1 个核心 ASIN 用 `full`，其余用 `basic`；分星抽样不能用于计算市场好评率。
10. 从 Amazon 低星缺陷为每个深验方向生成可解决的产品假设；TikTok 可见评论和达到独立父帖门槛的 Reddit 讨论只作补充。每个结论保留 `source_id`、原文、URL、父级 ID 与 `collection_mode`。
11. 按 [`references/opportunity-grading.md`](references/opportunity-grading.md) 对全部方向给出 A／B／C／D；未进入深验的方向必须标注“仅完成免费快筛”，不能把未调用 Sorftime／Amazon 写成验证失败。报告必须逐项解释为什么其他方向未进入 Top N。
12. 运行确定性脚本统计，先生成按渠道区分的内部 CSV，再合并为一个 `research_data.xlsx`；同时生成 Markdown 与可视化 HTML。数据文件契约见 [`references/report-contract.md`](references/report-contract.md)，主报告模板见 [`references/report-template.md`](references/report-template.md)，交付前执行 [`references/quality-checklist.md`](references/quality-checklist.md)。
13. 报告交付后主动给出 3～5 个可继续咨询的方向，例如深验更多候选、ASIN 对比、完整差评证据、产品打样规格或换市场重跑；等待用户选择，不自动扩大 Top N 或发布。

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

- 候选发现固定从 1 次类目搜索开始；若候选结果有分页，追加前先征得用户同意。
- 用户选择 Top N 后，每个深验方向至少 1 次商品搜索，因此最少调用数为 `候选发现页数 + N`。
- 每个方向商品搜索最多自动看到第 3 页，因此不含类目校正时，最坏调用数为 `候选发现页数 + 3 × N`。
- Top N 选择导致预计总调用超过 5 次时，必须先展示最少／最坏预算并获得确认；确认后的预算是本次任务上限，不得静默增加。
- 商品搜索准备进入任一方向第 4 页，或需要新增类目校正时，必须再次说明原因和边际收益。
- 默认不调用 `product_detail`、Sorftime `product_reviews` 或 `category_report`；Amazon 评论走 `bggg-data-amazon`。

## 最终交付

面向用户只交付 3 个文件：

1. `report/report.html`：主报告，按固定模板展示完整候选池、三个免费源快筛、每个淘汰理由、用户选择的 Top N、深验结果、代表 ASIN、真实痛点、产品机会、风险、证据与继续咨询入口。
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
