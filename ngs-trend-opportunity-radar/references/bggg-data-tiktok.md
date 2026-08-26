# bggg-data-tiktok（内置模块）

`bggg-data-tiktok` 是 `ngs-trend-opportunity-radar` 内部的数据采集模块，不作为独立 Skill 安装或要求用户单独调用。父 Skill 进入 TikTok 阶段时自动执行本模块。它吸收 `bggg-tiktok-search` 的真实 Chrome 思路，只采集用户已登录浏览器里公开或可见的页面，不点赞、关注、评论、私信或发布。

## 路由顺序

1. 优先运行本 Skill 的 `scripts/bggg_data_tiktok.py`，连接用户主动开启远程调试的 Chrome。
2. CDP 不可用时，使用当前环境的 Chrome 控制能力操作用户已登录的 TikTok：搜索、滚动、读取 DOM、截图，并按下方 JSONL 契约落盘。
3. 若出现登录、验证码、地区提示或风控，让用户手动处理后继续；不得绕过 CAPTCHA。
4. 两条路径都不可用时，记录失败原因。不得用搜索摘要、镜像站或虚构样本补齐门槛。

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

用户需要先自行启动带远程调试的 Chrome；该动作会打开新的 Chrome 实例，不能由 Agent 静默替换用户当前会话：

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --profile-directory="Default" \
  --no-first-run
```

检查连接：

```bash
python3 scripts/bggg_data_tiktok.py check
```

Top 5 快筛时，每个商品词单独搜索并写入同一个 JSONL：

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

Top 1～3 深验时，从已通过语义检查的视频中选择至少 5 个独立父视频，再批量抓可见评论；最终每个深验方向至少保留 100 条有效评论：

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

无法运行 CDP 脚本时，仍使用同一目录和 JSONL 字段。每个搜索词至少保存一张首屏或滚动后截图，并把 `collection_mode` 写为 `visible_dom_chrome`。手动整理不降低样本门槛；不足时按小样本降级。
