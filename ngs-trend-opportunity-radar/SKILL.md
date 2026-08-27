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
- 一次运行只研究一个用户给定品类。用户同时给出多个品类时，拆成多个独立运行目录，分别采集、统计并交付各自的 `report.html`、`research_data.xlsx`、`report.md`；不得合并成一份正式报告或工作簿。跨品类总览只能在全部单品类交付完成后作为可选附加件生成。
- Reddit 使用内置 `bggg-data-reddit` 模块；API 失败时正式回退到用户已登录的 `old.reddit.com`。可见 DOM 只能作为明确标记的小样本，不能冒充完整评论树。
- TikTok 采集只使用用户选定、已登录的真实 Chrome；内置模块只负责查询计划、页面可见数据规范化和落盘，不自行启动独立浏览器、不换匿名接口。语言只能证明语言匹配，不能单独证明地理市场。
- 首次调用展示 3 项业务信息（研究品类、目标市场、平台）和 1 项交付设置（输出位置）；只追问缺失项，不替用户默选。
- 首次使用若尚未连接 Sorftime，先给出配置入口 `https://open.sorftime.com/mcp`，提示用户注册并在当前 AI 工具的 MCP 设置中填写自己的 Sorftime Key，配置后只需回复“已配置”。可以说明“首次注册赠送 3 天、100 次调用”，同时注明活动以 Sorftime 页面最新规则为准。不要让用户把 Key 发到对话里，也不得把 Key 写进 Skill、报告、日志或交付包。
- 登录态是业务卡后的条件式闸门：有多个可用登录环境时必须让用户选择；不读取凭证、不静默混用账号。
- 默认只生成本地 Excel 工作簿、Markdown 与 HTML。用户确认标题、位置、收件群和机器人身份后，才读取 [`references/feishu-publishing.md`](references/feishu-publishing.md) 发布。

## 固定工作流

1. 读取 [`references/research-brief.md`](references/research-brief.md)，首次使用时先检查 Sorftime MCP，再展示并整理《趋势选品启动卡》。若 Sorftime 尚未连接，按 [`references/sorftime-budget.md`](references/sorftime-budget.md) 给出 `https://open.sorftime.com/mcp`，说明注册权益并提示用户在 MCP 设置中填写 Key；不接收明文 Key。复用用户已给信息，只追问研究品类、目标市场、平台和输出位置中的缺失项；不要追加售价、毛利、排除项或筛选范围。输出位置是交付设置，不是选品条件。若用户给了多个研究品类，先按品类拆成独立任务和独立输出目录，再逐个运行，不共用候选池或正式数据表。
2. 业务卡齐全后，按 [`references/login-session-routing.md`](references/login-session-routing.md) 只读检查可用登录环境。只有一个时回显；多个时先让用户选择统一环境或按 Google Trends／TikTok／Reddit 浏览器回退分配，选择前不采集。
3. 回显业务卡、登录态选择、三个免费源的固定快筛范围，以及 Sorftime 类目树预算。每个研究品类默认 5 次：1 次查看第一层、4 次展开用户确认的分支。用户可改为少于 4 个、超过 4 个或不展开；超过默认预算时先展示新增次数，确认后才调用。
4. 先判断研究品类粒度：`家居收纳`、`宠物清洁`这类业务品类进入官方类目树；`Home & Kitchen` 这类平台一级大类先让用户收窄，已具体到单一商品或 SKU 则跳过候选漏斗，改走单品验证。先用 Sorftime `category_name_search` 定位语义匹配的正式节点，必要时用 `category_tree` 从站点顶层逐级定位；不得用 `category_search_from_product_name` 代替业务品类的类目树枚举，也不得由模型凭经验拆名单。
5. 对定位到的正式节点调用一次 `category_tree`，展示直接下一层的数量、名称和 Node ID。若第一层超过 4 个，Agent 可基于与研究品类的语义相关性推荐 4 个，但必须让用户确认或改选；若不超过 4 个则展示全部。每个确认分支再调用一次 `category_tree` 读取下一层。展开只表示读取官方子节点，不等于市场规模、商品池或深验。
6. 默认把用户确认展开的父分支作为候选方向，其下一层节点用于解释范围和生成跨平台搜索词；不得把展开得到的所有孙节点静默膨胀成新的候选池。若用户希望逐个孙节点调研，先展示节点总数、额外 Sorftime 市场调用数和三个免费源的采集量，再让用户确认。每个候选保存 `source_category_node_ids`、`child_category_node_ids`、本地语言名称、跨平台搜索词和纳入理由。
7. 在跨平台排序前，对每个候选方向分别调用一次 Sorftime `category_report` 补齐 Top-100 月销量、月销售额、价格、集中度、评论门槛和退货率等可用市场字段；字段缺失保持缺失。重复、抽象需求、品牌词、非商品节点或语义偏题项进入 `excluded_directions` 并记录原因。不同节点返回相同或明显偏题结果时标记 `semantic_mismatch`，不得进入候选池。只有 `category_discovery_status=ready` 且每个候选已有有效市场规模或明确缺失原因，才能进入三源快筛。
8. 按 [`references/source-sample-ranges.md`](references/source-sample-ranges.md) 和 [`references/sample-gates.md`](references/sample-gates.md) 对每个候选方向统一运行三个免费源：Google Trends 看搜索需求，TikTok 看内容扩散与使用演示，Reddit 看社区讨论与真实场景。跨平台比较单位是“候选方向”，不是要求各平台存在同名类目。任何方向都不得因早期排名而跳过某一免费源。每个“找不到”必须区分 `blocked`、`empty`、`semantic_mismatch` 和真实弱信号；前两类不能写成零需求。
9. 免费快筛完成后先生成一套“快筛阶段三件套”：`report.html`、`research_data.xlsx`、`report.md`。报告必须明确写“等待用户选择 Top N”，逐方向展示 Sorftime 市场规模、三个免费来源状态、关键数字、卡点、保留／观察／收窄决定及理由；工作簿中尚未运行的 TikTok 评论、Reddit 评论、Sorftime 商品和 Amazon 评论表必须写明 `not_run` 与阶段原因，不能留成不知用途的空表。运行 `render_screening_report.py` 后停止，询问用户希望多少个方向进入深验；Top N 必须由用户明确选择，不默认为 Top 1。
10. 用户选择 Top N 后，按 [`references/sorftime-budget.md`](references/sorftime-budget.md) 计算最少与最坏调用数并确认预算。对所选方向复用候选阶段的类目报告，随后分别调用 `product_search` 取代表商品，语义筛选后每方向保留 3～10 个 ASIN。每方向默认最多看 3 页，达到 3～10 个即停止；第 4 页前再次确认。
11. 为每个深验方向分别创建 Amazon 目标，使用 `bggg-data-amazon` 抓 Amazon US 书面评论；每方向至少 100 条，正常目标 300～1000 条。优先 1 个核心 ASIN 用 `full`，其余用 `basic`；分星抽样不能用于计算市场好评率。
12. 从 Amazon 低星缺陷为每个深验方向生成可解决的产品假设；TikTok 可见评论和达到独立父帖门槛的 Reddit 讨论只作补充。每个结论保留 `source_id`、原文、URL、父级 ID 与 `collection_mode`。
13. 按 [`references/opportunity-grading.md`](references/opportunity-grading.md) 对全部方向给出 A／B／C／D；未进入深验的方向必须标注“已完成类目市场与免费快筛，未做商品／评论深验”，不能写成验证失败。报告必须逐项解释为什么其他方向未进入 Top N。
14. 运行确定性脚本统计，先生成按渠道区分的内部 CSV，再合并为一个 `research_data.xlsx`；同时生成 Markdown 与可视化 HTML。数据文件契约见 [`references/report-contract.md`](references/report-contract.md)，主报告模板见 [`references/report-template.md`](references/report-template.md)，交付前执行 [`references/quality-checklist.md`](references/quality-checklist.md)。
15. 报告交付后主动给出 3～5 个可继续咨询的方向，例如深验更多候选、ASIN 对比、完整差评证据、产品打样规格或换市场重跑；等待用户选择，不自动扩大 Top N 或发布。

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
python3 scripts/export_audit_csv.py --run-dir '<run>' --research-category '<research category>'
# 按 Spreadsheets Skill 提供的 Node 运行时和 @oai/artifact-tool 环境执行：
node scripts/build_research_workbook.mjs --run-dir '<run>' --report-label '<research category>'
python3 scripts/render_screening_report.py --run-dir '<run>' --research-category '<research category>' --out-dir '<run>/report'
python3 scripts/rank_candidates.py --input '<run>/analysis/candidates.json' --output '<run>/analysis/opportunity_pool.json'
python3 scripts/render_report.py --brief '<run>/00-research-brief/research_brief.json' --pool '<run>/analysis/opportunity_pool.json' --run-dir '<run>' --out-dir '<run>/report'
python3 scripts/validate_run.py --run-dir '<run>' --soft-call-cap '<displayed default budget>' --hard-call-cap '<user-approved cap>'
```

TikTok 必须在用户选定、已登录的真实 Chrome 中采集；内置 `bggg-data-tiktok` 只负责查询计划、可见数据规范化与落盘。内置 `bggg-data-reddit` 负责 Reddit API、`old.reddit.com` 回退与规范化；其余脚本负责去重、门槛判断、渲染和证据检查。查询语义／语言复核、痛点可解决性、产品假设与最终进入决策由 Agent 和用户完成。

## 默认调用额度

- 每个研究品类默认类目树预算为 5 次：1 次查看第一层、4 次展开用户确认的分支。用户可选择 0～全部分支；超出 5 次前先确认新增次数。
- 候选市场规模预算为 `候选方向数` 次 `category_report`，必须在三源快筛前展示；它不包含在 5 次类目树预算中。
- 用户选择 Top N 后，每个深验方向至少 1 次商品搜索，因此深验最少新增 `N` 次。
- 每个方向商品搜索最多自动看到第 3 页，因此深验最坏新增 `3 × N` 次。
- Top N 选择导致预计总调用超过 5 次时，必须先展示最少／最坏预算并获得确认；确认后的预算是本次任务上限，不得静默增加。
- 商品搜索准备进入任一方向第 4 页，或需要新增类目校正时，必须再次说明原因和边际收益。
- 默认不调用 `product_detail` 或 Sorftime `product_reviews`；全候选 `category_report` 是市场规模必需调用，Amazon 评论走 `bggg-data-amazon`。

## 最终交付

面向用户只交付 3 个文件：

1. `report/report.html`：主报告。快筛阶段展示完整候选池、六张实际数据图、每个方向的去留理由和 Top N 选择入口；深验阶段再增加代表 ASIN、Amazon 真实痛点、产品机会与风险。不得用深验模板伪装尚未运行的数据。
2. `report/research_data.xlsx`：唯一正式数据文件，含 10 个按渠道拆分的工作表，Reddit 帖子和评论独立成表。
3. `report/report.md`：方便复制、归档或确认后发布飞书的轻量文字版。

这三个文件只对应启动卡中的一个研究品类。多个品类必须各有一套三件套和独立目录，不能用跨品类混合工作簿代替；可选总览不属于单次运行的正式三件套。

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
