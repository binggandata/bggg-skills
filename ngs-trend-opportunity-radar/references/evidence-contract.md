# 证据契约

## 趋势信号行

`data/signals/*.jsonl` 每行至少包含：

```json
{
  "theme": "drawer organizer",
  "platform": "TikTok",
  "signal_type": "visible_video",
  "source_id": "sha256-or-native-id",
  "url": "https://...",
  "observed_at": "2026-08-24T10:00:00+08:00",
  "requested_market": "US",
  "observed_market": "unknown",
  "query_semantic_status": "matched",
  "text_raw": "exact visible text",
  "value": null
}
```

- `text_raw` 保留原文，不在原始层翻译或改写。
- `source_id`、`url`、`observed_at` 缺一项，不能作为 A／B 级关键证据。
- 数值必须带单位和含义；Google Trends 指数、互动量、销量不得混入同一字段后直接相加。
- `query_semantic_status` 使用 `matched`、`ambiguous`、`mismatch` 或 `not_checked`；只有 `matched` 可以满足 A／B 的趋势平台门槛。

TikTok 采集器先把可见视频／评论写入 `data/raw/tiktok_*.jsonl`。Agent 完成语言与查询语义抽查后，才把通过的视频提升为上述 `data/signals/tiktok.jsonl` 趋势信号；原始层的 `not_checked` 不能直接进入评分。

Reddit 采集器把 API 与 old Reddit 可见数据写入 `data/raw/reddit*.jsonl`。提升为趋势信号前，除通用字段外还要保留 `context.post_id`、`subreddit`、`collection_mode` 和父帖门槛状态；仅有一个父帖时不能满足 Reddit 快筛门槛。

## 痛点证据

每条痛点证据至少包含：`source_id`、平台、内容类型、原文、URL、日期或日期缺失标记、主题、痛点标签、场景、是否可解决、判断依据。

同一帖子、视频或 Listing 下的多条评论属于同一父级证据簇。做“高频”判断时必须披露父级集中度，不能让一个病毒帖制造虚假普遍性。

## Sorftime 调用日志

`sorftime/call_log.jsonl` 每行记录：

```json
{
  "tool": "category_search_from_product_name",
  "candidate_id": "theme-001",
  "arguments_redacted": {"product_name": "drawer organizer", "amz_site": "US"},
  "called_at": "2026-08-24T10:00:00+08:00",
  "reason": "default_top3_validation",
  "success": true,
  "response_file": "sorftime/theme-001_category.json"
}
```

禁止记录 MCP Key、Cookie、Token 或浏览器凭证。

## 证据独立性

- 不同平台可以算独立来源。
- 同一内容被搬运到多个平台，若能识别出同源，只算一条原始信号。
- 同一父帖／视频／ASIN 下的多条评论不等于多个独立市场来源。
- 搜索引擎摘要只能发现 URL，不能成为引用原文。
