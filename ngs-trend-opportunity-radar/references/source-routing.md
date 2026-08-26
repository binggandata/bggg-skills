# 数据源路由与市场边界

## 登录优先

外部采集前先执行 [`login-session-routing.md`](login-session-routing.md)。用户选定登录环境后，Google Trends、TikTok 直接走该环境；Reddit 先走结构化 API，受阻时使用用户确认的 `old.reddit.com` 登录环境。Sorftime 使用 MCP；Amazon 评论使用 `bggg-data-amazon`，不参与浏览器登录态选择。

## 趋势发现

| 来源 | 回答的问题 | 默认路线 | 不能声称 |
|---|---|---|---|
| Google Trends | 搜索兴趣是否上升、季节性与拐点 | 用户选定的登录浏览器页面；或用户导出。记录 geo、窗口和查询词 | 相对指数等于销量 |
| TikTok | 内容供给、近期传播与反复出现的场景 | 用户选定登录环境 + 内置 `bggg-data-tiktok`，或按其浏览器回退流程采可见 DOM | 热门视频等于购买需求 |
| Reddit | 独立社区是否持续讨论同一使用场景、替代方案与痛点 | 内置 `bggg-data-reddit`：OAuth／公共 JSON API → 已登录 `old.reddit.com` 同源 JSON → old Reddit 可见 DOM | 单个帖子或一个 subreddit 等于北美普遍需求 |
| Sorftime | 类目商业快照和 Top 商品池 | 1 次类目搜索 + Top 1 的 1 次商品搜索 | 搜索结果等于完整市场 |
| Amazon | 代表 ASIN 的真实买后缺陷 | `bggg-data-amazon` 书面评论 | 分星样本等于真实好评率 |

趋势主题进入痛点验证前，优先要求至少两个独立来源同向；同一平台的多个查询不是多个独立平台。

### 查询语义门槛

趋势词在计入候选前必须标记 `query_semantic_status`：

- `matched`：结果主体与预期商品／场景一致，可以计入趋势平台数。
- `ambiguous`：结果混有机构名、教程、人物账号或其他同形词，只能作弱线索，不能满足 A／B 的跨平台门槛。
- `mismatch`：结果主体与候选商品无关，不计入趋势证据。
- `not_checked`：尚未人工抽查，按缺失处理。

抽查至少看首屏结果类型和 3 条可见结果。宽词（例如 `home organization`）若同时指“家居收纳”和“组织机构”，应换成商品词／场景词重查；不能仅凭曲线存在就判定商品需求。

## 痛点验证

- TikTok 评论：即时追问、抱怨、购买意图；使用内置 `bggg-data-tiktok` 的 `scripts/bggg_data_tiktok.py comments`，只抓选定父视频的可见评论。
- Reddit 评论：使用内置 `bggg-data-reddit`；只有达到独立父帖门槛的 JSON／old Reddit DOM 样本才能进入痛点验证，且按父帖计算集中度。
- Amazon 评论：Top 1 品类进入具体产品阶段后的必做买后验证；使用 `bggg-data-amazon`。该 Skill 仅覆盖 Amazon US 书面评论。
- 非美 Amazon 市场没有可靠评论入口时，允许用户提供 CSV／XLSX／JSONL，或把 Amazon 评论证据标为缺失；不得静默用美国评论代替目标市场。

## 市场支持规则

“任何市场都可以”表示任务卡允许任意市场，不代表每个数据源都能精确定位任意市场。

1. 每条证据同时记录 `requested_market` 与 `observed_market`。
2. TikTok Chrome 内容受账号、语言、位置和推荐系统影响；语言只证明语言匹配，市场参数是研究意图，不是地理证明。
3. Sorftime TikTok 结构化工具只在 Schema 支持的站点使用；不支持的市场不得自行映射到相邻国家。
4. 数据源不覆盖目标市场时，可用于“跨市场启发”，但不能进入该市场的强验证列。

## 降级

统一状态、重试和 Sorftime 翻页停止规则见 [`degradation-and-pagination.md`](degradation-and-pagination.md)。

- Google Trends 无法读取：若尚未走选定登录环境，切换后只重试 1 次；仍失败则保留查询计划，使用其他平台，不补造指数。
- TikTok 搜索或评论被阻断：按 [`bggg-data-tiktok.md`](bggg-data-tiktok.md) 回退；仍失败则保留已采集包与失败日志，视频趋势和评论缺口分开写。
- TikTok／Amazon 评论不足：降低痛点置信度，不用搜索摘要替代原文。
- Reddit API 被阻断：按 [`bggg-data-reddit.md`](bggg-data-reddit.md) 切换到已登录 `old.reddit.com`；`.json` 仍被阻断时采明确标记的可见 DOM。所有路线失败则记为 `blocked`，不能写成没有讨论。
- Sorftime 不支持目标站点：输出“商业验证缺失”，仍可形成 C 级观察项，但不能因缺失自动升级。
