# NGS 多平台趋势选品

[English](./README_EN.md)

`ngs-trend-opportunity-radar` 是一个面向跨境电商的 Codex Skill。它先用 Sorftime 官方类目树定位研究品类，让用户确认要展开的分支，再为每个候选方向补市场规模，并让 Google Trends、TikTok、Reddit 覆盖全部候选。用户查看漏斗后选择 Top N，Skill 再用 Sorftime 商品与 Amazon 书面评论深验。

一次运行只研究一个品类。若同时研究家居收纳和宠物清洁，会拆成两个独立运行目录，分别输出各自的 HTML、Excel 和 Markdown，不把数据混成一份正式成果。

它不是爆款承诺，也不替代打样、成本、合规和最终上架判断。

## 能做什么

1. 用 Sorftime 官方类目树展示研究品类下的正式子类目，并让用户选择展开分支。
2. 保留全部语义相关、可对应具体商品的方向，并说明排除项。
3. 对全部有效方向运行 Google Trends、TikTok 和 Reddit 快筛。
4. 逐方向说明通过项、卡点、保留／淘汰决定和原因。
5. 由用户选择进入深验的 Top N，不替用户默选数量。
6. 对 Top N 搜索代表商品，并用 Amazon US 书面评论分析买后问题。
7. 输出全候选 A／B／C／D 等级与深验方向的产品改良建议。
8. 生成自包含 HTML 报告、10 工作表 Excel 和 Markdown。
9. 多品类需求按品类拆分运行和交付；跨品类总览仅作为可选附加件。

## 固定工作流

```text
首次配置 Sorftime MCP
→ 填写趋势选品启动卡
→ Sorftime 官方类目树展示第一层
→ 用户确认分支（默认展开 4 个）
→ 每个候选方向补 Sorftime 市场规模
→ 全部候选方向跑 Google Trends／TikTok／Reddit
→ 输出快筛阶段三件套：HTML／Excel／Markdown
→ 用户选择 Top N
→ Top N 做 Sorftime 商品与 Amazon 多 ASIN 评论深验
→ A／B／C／D 机会池与产品改良方向
```

如果用户给出多个研究品类，上述流程会对每个品类完整执行一次。不同品类不共享候选池、样本计数、证据索引或正式工作簿。

## 首次使用

### 1. 配置 Sorftime MCP

打开：<https://open.sorftime.com/mcp>

注册并按页面说明把自己的 Sorftime Key 配置到当前 AI 工具的 MCP 设置中。首次注册赠送 3 天、100 次调用；活动可能调整，以 Sorftime 页面最新规则为准。

不要把 Key 发到对话、Issue、日志、报告或 Skill 文件中。配置完成后，只需在对话中回复“已配置”。

### 2. 填写启动卡

```text
【趋势选品启动卡】

1. 研究品类：
2. 目标市场：
3. 销售平台：
4. 输出位置：
```

也可以直接回复：

```text
家居收纳｜美国｜Amazon｜桌面/趋势选品报告
```

Agent 会先回显登录环境、市场边界和类目树预算，不会先凭经验拆方向。每个研究品类默认 5 次类目树调用：1 次查看第一层、4 次展开用户确认的分支；用户可以少选、多选或不展开。展开后按确认的父分支形成候选方向，每个候选补 1 次市场报告，再运行三个免费源。快筛完成后，用户再选择 Top N 和深验预算。

快筛完成时已经会生成正式三件套，而不是只返回一张表。报告明确标注“等待选择 Top N”；Excel 中尚未运行的 TikTok 评论、Reddit 评论、Sorftime 商品和 Amazon 评论工作表会写明 `not_run` 与原因。选择 Top N 后，同一套文件再升级为深验版本。

## 安装

需要 Python 3.10 或更高版本。

克隆 `bggg-skills`：

```bash
git clone https://github.com/binggandata/bggg-skills.git
cd bggg-skills
```

复制本 Skill 及其 Amazon 评论采集依赖：

```bash
mkdir -p ~/.codex/skills
cp -R ngs-trend-opportunity-radar bggg-data-amazon ~/.codex/skills/
```

开发时可以软链接：

```bash
ln -s "$PWD/ngs-trend-opportunity-radar" ~/.codex/skills/ngs-trend-opportunity-radar
ln -s "$PWD/bggg-data-amazon" ~/.codex/skills/bggg-data-amazon
```

TikTok CDP 采集脚本需要 Python Playwright：

```bash
python3 -m pip install -r ngs-trend-opportunity-radar/scripts/requirements.txt
```

本 Skill 的 Amazon 评论采集依赖同仓库的 `bggg-data-amazon`。Excel 构建使用 Codex Spreadsheets 运行时提供的 `@oai/artifact-tool`；在 Codex 之外运行时，需要自行提供兼容的工作簿构建环境。

## 调用

```text
调用 ngs-trend-opportunity-radar，帮我做多平台趋势选品。
```

或者：

```text
调用 ngs-trend-opportunity-radar。
研究品类：宠物清洁
目标市场：美国
平台：Amazon
输出位置：桌面/宠物选品报告
```

## 默认样本门槛

| 平台 | 全候选快筛 | 用户所选 Top N 深验 |
| --- | --- | --- |
| Google Trends | 全部有效方向；每词近 12 个月、53 周 | 可补看近 5 年季节性 |
| TikTok | 每方向至少 10 个相关视频、5 个账号 | 默认不追加百评门槛 |
| Reddit | 每方向至少 10 篇独立相关帖 | 默认不追加百评门槛 |
| Sorftime | 官方类目树＋每个候选 1 次市场报告 | 每个深验方向搜索代表商品 |
| Amazon | 快筛阶段不采集 | 每方向 3～10 个代表 ASIN；至少 100 条书面评论 |

数量只是覆盖门槛。查询语义、父内容独立性、最大父内容占比和目标市场边界仍需单独检查。

## Sorftime 调用预算

- 每个研究品类默认 5 次类目树调用：1 次看第一层、4 次展开确认分支；用户可改选。
- 全候选市场规模每方向 1 次，与类目树预算分开计算。
- 用户选择 Top N 后，商品池最少新增 N 次，最多新增 3 × N 次。
- 预计超过 5 次时，必须展示最少／最坏预算并征得用户同意。
- 默认不调用 `product_detail` 或 `product_reviews`；`category_report` 用于全部候选的市场规模。

## Reddit 与登录态

Reddit 固定路线：

```text
OAuth（如已配置）
→ www.reddit.com 公共 JSON
→ 用户确认的已登录 old.reddit.com 同源 JSON
→ 已登录 old Reddit 可见 DOM
```

匿名 API 不访问 old Reddit。403、登录墙、challenge 或非 JSON 响应只代表当前路线失败，不代表市场没有需求。

## 输出

正式交付只有三个文件：

```text
report/report.html
report/research_data.xlsx
report/report.md
```

Excel 固定包含 10 个工作表：数据覆盖、Google Trends、TikTok 视频、TikTok 评论、Reddit 帖子、Reddit 评论、Sorftime 品类、Sorftime 商品、Amazon 评论、证据索引。

快筛阶段和深验阶段都使用这三个文件、同一套工作表结构：前者用于选 Top N，后者增加代表 ASIN、Amazon 低星痛点和产品改良方向。

每套三件套只属于一个研究品类。多个品类会得到多个独立目录；任何跨品类总览都不能替代这些单品类成果。

开发脚本在导出和渲染时显式接收研究品类，工作簿标题也写入该品类，避免从混合开发素材中误带其他品类。

原始 JSON／JSONL、内部 CSV、失败日志、截图和校验文件保留在用户选择的运行目录中，不提交到仓库。

## 安全与隐私

- 不保存 Sorftime Key、Reddit Token、Cookie、密码或浏览器凭证。
- 多个浏览器登录环境同时存在时，必须让用户选择。
- TikTok 脚本只导航、滚动和读取可见页面，不点赞、评论、关注、私信或发布。
- 不绕过 CAPTCHA、challenge、风控或平台登录墙。
- 报告图片只接受公开 HTTP(S) 地址，并拒绝 localhost、回环、私网和链路本地 IP。
- `outputs/`、`node_modules`、缓存、压缩包和本地运行数据均由 `.gitignore` 排除。

请遵守适用法律、站点条款和所在组织的数据治理要求。

## 开发与测试

```bash
python3 -m unittest discover -s ngs-trend-opportunity-radar/tests -p 'test_*.py'
```

当前测试数：37。

结构校验：

```bash
python3 "$CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py" \
  ngs-trend-opportunity-radar
```

## 免责声明

本项目用于研究和决策辅助，不构成销量、利润、合规、投资或上架保证。Google、TikTok、Reddit、Sorftime 和 Amazon 的名称与商标归各自权利人所有；本项目是独立工作流，与这些平台不存在官方隶属关系。

## License

MIT，见 [LICENSE](./LICENSE)。
