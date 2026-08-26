# NGS 多平台趋势选品

[English](./README_EN.md)

`ngs-trend-opportunity-radar` 是一个面向跨境电商的 Codex Skill。它从用户给定的大品类中拆出 5～10 个商品方向，用 Google Trends、TikTok、Reddit、Sorftime 和 Amazon 书面评论交叉验证，最终输出一个可追溯的产品机会池和 Top 1 方向。

它不是爆款承诺，也不替代打样、成本、合规和最终上架判断。

## 能做什么

1. 从用户确认的大品类生成 5～10 个具体商品子方向。
2. 用 Google Trends 比较目标市场的搜索变化和季节性。
3. 用 TikTok 可见视频与评论验证内容趋势和使用场景。
4. 用 Reddit 独立帖子与评论补充社区场景和替代方案。
5. 用 Sorftime 验证类目商业快照与代表商品。
6. 用 Amazon US 书面评论分析真实买后问题。
7. 按透明规则输出 A／B／C／D 机会等级。
8. 生成自包含 HTML 报告、10 工作表 Excel 和 Markdown。

## 固定工作流

```text
首次配置 Sorftime MCP
→ 填写趋势选品启动卡
→ 拆出 5～10 个商品子方向
→ Google Trends 搜索趋势快筛
→ TikTok 与 Reddit 内容／场景验证
→ Sorftime 类目与代表商品验证
→ Amazon 多 ASIN 书面评论验证
→ A／B／C／D 机会池与产品改良方向
```

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

Agent 会先回显候选方向、登录环境、各平台样本范围、市场覆盖边界和 Sorftime 调用预算。用户确认“开始”后，才会采集数据或调用付费接口。

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
研究品类：宠物用品
目标市场：美国
平台：Amazon
输出位置：桌面/宠物选品报告
```

## 默认样本门槛

| 平台 | Top 5 快筛 | Top 1 深验 |
| --- | --- | --- |
| Google Trends | 全部 5～10 个候选；每词近 12 个月、53 周 | Top 1 补看近 5 年季节性 |
| TikTok | 每方向至少 10 个相关视频、5 个账号 | 至少 20 个视频、5 个父视频、100 条有效评论 |
| Reddit | 每方向至少 10 篇独立相关帖 | 至少 10 篇帖子、5 个评论父帖、100 条有效评论 |
| Sorftime | 不对所有候选付费深挖 | Top 1 默认 1 次类目搜索 + 1 次商品搜索 |
| Amazon | Top 1 后才采集 | 3～10 个代表 ASIN；至少 100 条书面评论 |

数量只是覆盖门槛。查询语义、父内容独立性、最大父内容占比和目标市场边界仍需单独检查。

## Sorftime 调用预算

- 正常 Top 1：2 次。
- 商品语义不足时，最多自动看到第 3 页：最坏 4 次。
- 默认硬上限：5 次。
- 超过 5 次或准备进入商品第 4 页：必须再次征得用户同意。
- 默认不调用 `product_detail`、`product_reviews` 或 `category_report`。

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

当前测试数：31。

结构校验：

```bash
python3 "$CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py" \
  ngs-trend-opportunity-radar
```

## 免责声明

本项目用于研究和决策辅助，不构成销量、利润、合规、投资或上架保证。Google、TikTok、Reddit、Sorftime 和 Amazon 的名称与商标归各自权利人所有；本项目是独立工作流，与这些平台不存在官方隶属关系。

## License

MIT，见 [LICENSE](./LICENSE)。
