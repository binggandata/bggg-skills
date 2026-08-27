# 内置 bggg-data-reddit

本模块把 Reddit 社区讨论纳入趋势选品证据链。它优先保存结构化 JSON；API 受阻时正式回退到用户已登录的 `old.reddit.com`，不使用搜索引擎摘要代替原帖或评论。

## 固定路线

1. 用 `bggg_data_reddit_plan.py` 从 `config/reddit_queries.tsv` 生成确定性请求计划。
2. 用 `bggg_data_reddit_api.py` 依次尝试：官方 OAuth API（已配置时）→ `www.reddit.com` 公共 JSON。匿名 API 采集不得请求 `old.reddit.com`。
3. API 全部失败时，切到用户确认的已登录浏览器。在 `old.reddit.com` 标签页优先同源请求搜索／评论 `.json`；进入 old Reddit 后必须使用该登录态。
4. 只有评论 `.json` 被 `ERR_BLOCKED_BY_CLIENT`、但普通 old Reddit 评论页可见时，才采 `visible-dom-1.0` 包。
5. JSON 与可见 DOM 分别规范化，随后按 `source_id`／`native_id` 去重；保留 `collection_mode`。
6. 人工复核父帖语义，写入 `config/reddit_relevance.tsv`；运行 `analyze_reddit_samples.py`，由原始行确定性计算快筛／深验门槛。

OAuth 可从本地环境读取 `REDDIT_ACCESS_TOKEN`，或 `REDDIT_CLIENT_ID`＋`REDDIT_CLIENT_SECRET`。不得把这些值写进任务卡、运行目录、清单、截图或报告。没有 OAuth 配置不是错误，继续尝试公共 JSON 与 old Reddit。

## old Reddit 可见 DOM 包

每个父帖保存到 `work/reddit/visible_dom/`，至少包含：

- `schema_version=visible-dom-1.0`；
- 查询词、父帖 URL、采集时间和 `json_route_status`；
- 父帖的 `native_id`、标题、正文、subreddit、日期；
- 每条可见评论的 `native_id`、`parent_native_id`、原文、日期、作者、permalink；
- `stop_reason`，例如可见评论上限、页面到底或未展开折叠节点。

这种包是可审计小样本，不是完整评论树。报告必须披露“可见 DOM”、父帖数、评论数、最大父帖占比和停止原因。

## 状态

- `success`：计划请求成功且没有路线失败。
- `partial`：拿到部分数据，但有请求或路线失败。
- `blocked`：结构化 API 没有拿到可用 JSON，进入 old Reddit 浏览器回退。
- `empty`：请求成功但没有返回帖子；先检查查询语义与时间窗口，不能直接写成需求为零。
- `semantic_mismatch`：返回内容与商品方向不符；不得进入趋势平台计数。

同一路线的瞬时 429／5xx／网络异常最多重试 1 次。登录墙、challenge、403、非 JSON 响应或 `ERR_BLOCKED_BY_CLIENT` 立即记录并切换下一条路线，不循环刷新。

## 进入评级

- 全候选快筛：每个有效方向至少 10 个语义相关独立帖子；同一转帖链只算一个父级，不得因早期排名跳过方向。
- 用户选择 Top N 后，已有评论可作补充证据；默认不再要求 Reddit 百条评论作为深验门槛。
- Reddit 只说明社区讨论与语言／subreddit 语境，不能单独证明目标地理市场。
- 未达到快筛门槛时，Reddit 不计入独立趋势平台；`blocked`、`empty` 与语义弱信号必须分别披露。

`config/reddit_relevance.tsv` 至少包含 `native_id`、`theme`、`query_semantic_status`。只有 `matched`／`relevant` 父帖进入统计。`analysis/reddit_sample_gates.json` 分开记录相关帖子数 `parent_posts` 与实际评论覆盖父帖数 `comment_parent_posts`；前者控制快筛，后者控制深验。候选中的 `reddit_sample_gate_status` 和 `reddit_sample_gate_detail` 必须与它一致，校验器会复核，不能手填绕过。

规范化行必须保留 `source_id`、`native_id`、`text_raw`、URL、query、post_id、subreddit、采集时间、`collection_mode` 与原始文件。
