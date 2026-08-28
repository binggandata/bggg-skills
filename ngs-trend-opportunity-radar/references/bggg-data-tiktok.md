# bggg-data-tiktok（内置模块）

`bggg-data-tiktok` 是 `ngs-trend-opportunity-radar` 内部的数据整理模块，不作为独立 Skill 安装或要求用户单独调用。TikTok 页面必须由用户选定、已登录的真实 Chrome 打开；本模块只生成查询计划、读取该 Chrome 的可见页面并规范化落盘，不自行启动独立浏览器，不切换匿名接口，不点赞、关注、评论、私信或发布。

## 路由顺序

1. 优先连接用户确认的真实 Chrome。若当前环境尚未接入，在该 Chrome 打开 `chrome://inspect/#remote-debugging`，勾选“Allow remote debugging for this browser instance”，并由用户同意连接弹窗；随后使用当前环境提供的 Chrome 控制能力读取同一浏览器会话。
2. 内置脚本只能作为该真实 Chrome 的读取与落盘适配层，不能启动 Playwright 独立浏览器、临时 Profile 或匿名 TikTok 会话。
3. 若出现登录、验证码、地区提示或风控，让用户手动处理后继续；不得绕过 CAPTCHA。
4. 用户 Chrome 无法连接时，记录失败原因并请用户完成浏览器设置。不得用应用内浏览器、搜索摘要、镜像站或虚构样本补齐门槛。

`bggg-tiktok-downloader`、`bggg-tiktok-readvideo`、`bggg-tiktok-cut` 和 `bggg-tiktok-capcut` 不属于默认趋势采集链。只有用户在报告后明确要求下载或深拆具体视频时，才另行使用相应能力。

## 内置文件与落盘结构

本模块由父 Skill 内的 3 个脚本组成：

- `scripts/bggg_data_tiktok_plan.py`：把多个商品词变成有上限的请求计划。
- `scripts/bggg_data_tiktok.py`：读取用户 Chrome 的可见视频卡片和评论；每个查询／父视频立即保存不可覆盖的原始包，同时更新规范化 JSONL。
- `scripts/bggg_data_tiktok_normalize.py`：从全部原始包重建规范化 JSONL 和汇总，供审计或重跑使用。

```text
<run>/
  config/tiktok_queries.tsv
  config/keywords.txt
  work/tiktok/request_plan.json
  work/tiktok/source_json/*.json
  work/tiktok/source_manifest.jsonl
  work/tiktok/failure_log.jsonl
  work/tiktok/normalize_summary.json
  data/raw/tiktok_<date>.jsonl
```

先为本次候选词生成计划：

```bash
python3 scripts/bggg_data_tiktok_plan.py \
  --queries '<run>/config/tiktok_queries.tsv' \
  --output '<run>/work/tiktok/request_plan.json'
```

## Chrome CDP

若用户选择 Chrome 远程调试，直接在用户当前 Chrome 打开：

```text
chrome://inspect/#remote-debugging
```

勾选“Allow remote debugging for this browser instance／允许此浏览器实例进行远程调试”，出现“要允许远程调试吗？”弹窗时由用户点“允许”。不能由 Agent 静默启动独立 Chrome、临时 Profile 或替换用户当前会话。

若环境使用本 Skill 的旧式 CDP 脚本，可再检查连接：

```bash
python3 scripts/bggg_data_tiktok.py check
```

全候选快筛时，每个有效商品方向都单独搜索并写入同一个 JSONL，不得因早期排名跳过：

```bash
python3 scripts/bggg_data_tiktok.py search \
  --query "drawer organizer" \
  --requested-market US \
  --language en \
  --limit 10 \
  --output '<run>/data/raw/tiktok_<date>.jsonl' \
  --screenshot-dir '<run>/quality/tiktok-screenshots' \
  --append
```

若页面自然暴露可见评论，可以对用户选择的 Top N 保留补充评论；默认不再要求 TikTok 百条评论作为深验门槛：

```bash
python3 scripts/bggg_data_tiktok.py comments \
  --video-url 'https://www.tiktok.com/@a/video/1' 'https://www.tiktok.com/@b/video/2' \
  --requested-market US \
  --language en \
  --limit-per-video 40 \
  --output '<run>/data/raw/tiktok_<date>.jsonl' \
  --screenshot-dir '<run>/quality/tiktok-screenshots' \
  --append
```

若需要从原始包重新生成统一 JSONL：

```bash
python3 scripts/bggg_data_tiktok_normalize.py \
  --inputs '<run>/work/tiktok/source_json/*.json' \
  --output '<run>/data/raw/tiktok_<date>.jsonl' \
  --summary '<run>/work/tiktok/normalize_summary.json' \
  --keywords '<run>/config/keywords.txt'
```

## 输出契约

每行是一个视频或评论，至少包含：

```json
{
  "platform": "TikTok",
  "content_type": "video",
  "source_id": "tiktok-video-123",
  "native_id": "123",
  "date": null,
  "text_raw": "页面可见原文",
  "engagement": {"views": 12000, "likes": null, "comments": null},
  "context": {
    "query": "drawer organizer",
    "requested_market": "US",
    "observed_market": "unknown",
    "language": "en",
    "language_match": "not_checked",
    "query_semantic_status": "not_checked",
    "url": "https://www.tiktok.com/@a/video/123",
    "parent_video_id": "123",
    "collection_mode": "visible_dom_cdp",
    "source_file": "data/raw/tiktok_<date>.jsonl"
  }
}
```

- 原始层的 `language_match` 和 `query_semantic_status` 默认是 `not_checked`；Agent 抽查首屏和至少 3 条结果后才可改为 `matched`、`ambiguous` 或 `mismatch`。
- `observed_market` 默认 `unknown`。语言匹配不能改写成地理市场匹配。
- 评论必须保留 `parent_video_id`；同一父视频的多条评论属于一个证据簇。
- 多次采集写同一文件时按 `source_id` 去重；截图仅作页面状态证明，JSONL 原文才进入统计。
- 原始包不覆盖：同一查询或视频重试时递增 `attempt_01`、`attempt_02`；`source_manifest.jsonl` 保留每次行数、时间和停止原因。

## 停止条件

- 登录墙、验证码、挑战页、可疑登录或限流。
- 页面明显有内容但提取为零，或字段与截图不一致。
- 达到样本上限或连续多轮无新增。
- 用户中断。

停止后保留已完成原始包并写失败日志。第三方付费采集器只有在用户已有 Key、明确批准费用并指定后端时才可使用；默认不安装、不调用、不自动切换。

## 人工浏览器回退

无法运行 CDP 脚本时，仍只操作用户确认的真实 Chrome，并使用同一目录和 JSONL 字段。每个搜索词至少保存一张首屏或滚动后截图，并把 `collection_mode` 写为 `visible_dom_chrome`。手动整理不降低样本门槛；不足时按小样本降级。
