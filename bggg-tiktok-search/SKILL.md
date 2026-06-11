---
name: bggg-tiktok-search
description: >
  使用本地真实 Chrome 登录态做 TikTok 调研，支持 WebBridge、Chrome/CDP、Apple Events 或人工辅助路径。
  当用户要求在 TikTok 上搜索关键词、搜索博主、采样视频、打开博主主页、
  采集最近作品、提取视频链接/标题/作者/互动指标、截图留证、
  输出 CSV/Markdown/JSON 调研包，或做 TikTok 博主/内容/选题/带货方向研究时，
  使用此 skill。它不依赖第三方 TikTok API，核心原则是只做可见页面读取、滚动、截图和结构化整理。
---

# BGGG TikTok Search

## 目标

用用户本地真实 Chrome 的 TikTok 登录态完成内容调研、博主搜索、视频采样、主页采集和截图留证。默认只读取公开或用户可见页面，不做点赞、关注、评论、私信、发布或账号设置修改。

## 前置条件

任选一种控制路径：

1. WebBridge：本地 WebBridge daemon 和浏览器扩展可用。
2. Chrome/CDP：用户自己启动带 remote debugging 的 Chrome，脚本通过 Playwright 连接。
3. Apple Events：macOS Chrome 开启 `View > Developer > Allow JavaScript from Apple Events` 后使用 `scripts/tk_real_chrome.py`。
4. 手动辅助：当登录、验证码、地区弹窗或风控出现时，让用户在真实 Chrome 里处理后继续。

WebBridge 健康检查：

```bash
WEBBRIDGE_URL="${WEBBRIDGE_URL:-http://127.0.0.1:10086}"
curl -s "$WEBBRIDGE_URL/status"
```

CDP 健康检查：

```bash
python3 <skill-dir>/scripts/tk_research.py check-cdp
```

## 工作流

1. **判断任务类型**：
   - 关键词找视频 → `search`
   - 关键词找博主 → `authors`
   - 已有博主主页 → `creator`
   - 用户已经把 Chrome 打到目标页 → `current`
2. **操作 Chrome**：
   - `navigate` 打开 TikTok 搜索页/博主页。
   - `fill` 输入搜索词，`click` 触发搜索。
   - `snapshot` 读取页面内容，定位视频卡片。
   - `evaluate` 提取结构化数据（URL、作者、标题、互动数）。
   - 截图留证，避免把 base64 截图直接贴进上下文。
   - 滚动加载更多，重复提取。
3. **结果保存**：
   - 结构化数据写入 `collected_items.json`。
   - 截图保存到 `screenshots/`。
   - 生成 `research_notes.md` 做业务蒸馏。
4. **后续衔接**：
   - 要下载视频 → 交给 `bggg-tiktok-downloader`
   - 要分析视频 → 交给 `bggg-tiktok-readvideo`

## WebBridge 操作示例

### 1. 打开 TikTok 并搜索关键词

```bash
# 打开 TikTok 首页（新标签页，session 隔离）
curl -s -X POST "$WEBBRIDGE_URL/command" \
  -H 'Content-Type: application/json' \
  -d '{"action":"navigate","args":{"url":"https://www.tiktok.com","newTab":true,"group_title":"TikTok Research"},"session":"tiktok-search"}'

# 获取页面 snapshot，找到搜索框的 @e ref
curl -s -X POST "$WEBBRIDGE_URL/command" \
  -d '{"action":"snapshot","session":"tiktok-search"}'

# 在搜索框填入关键词（用 @e ref 或 CSS selector）
curl -s -X POST "$WEBBRIDGE_URL/command" \
  -d '{"action":"fill","args":{"selector":"input[type=search]","value":"skincare routine"},"session":"tiktok-search"}'

# 点击搜索按钮或按回车
curl -s -X POST "$WEBBRIDGE_URL/command" \
  -d '{"action":"click","args":{"selector":"button[type=submit]"},"session":"tiktok-search"}'
```

### 2. 提取视频卡片数据

```bash
# 用 evaluate 提取视频列表的结构化数据
curl -s -X POST "$WEBBRIDGE_URL/command" \
  -d '{"action":"evaluate","args":{"code":"(() => { const cards = [...document.querySelectorAll(\"[data-e2e=search-card-video]\")].slice(0, 10); return cards.map((c, i) => { const link = c.querySelector(\"a\"); const author = c.querySelector(\"[data-e2e=search-card-user-avatar]\"); const metrics = [...c.querySelectorAll(\"[data-e2e=video-views]\")]; return { index: i, url: link ? link.href : null, title: c.innerText.slice(0, 200), author: author ? author.getAttribute(\"href\") : null, raw_text: c.innerText.slice(0, 500) }; }); })()"},"session":"tiktok-search"}'
```

> TikTok DOM 经常变化，上面的 selector 只是示例。实际使用时先用 `snapshot` 读当前页面结构，再写对应的 `evaluate` 提取逻辑。

### 3. 截图留证

```bash
python3 <skill-dir>/scripts/tk_research.py screenshot "search_001"
```

### 4. 滚动加载更多

```bash
curl -s -X POST "$WEBBRIDGE_URL/command" \
  -d '{"action":"evaluate","args":{"code":"window.scrollTo(0, document.body.scrollHeight); return document.body.scrollHeight;"},"session":"tiktok-search"}'
```

滚动后等待 2-3 秒让内容加载，再 `snapshot` 或 `evaluate` 提取新出现的卡片。

### 5. 打开博主主页采集作品

```bash
# 导航到博主主页
curl -s -X POST "$WEBBRIDGE_URL/command" \
  -d '{"action":"navigate","args":{"url":"https://www.tiktok.com/@creator","newTab":true},"session":"tiktok-creator"}'

# 提取主页视频列表
curl -s -X POST "$WEBBRIDGE_URL/command" \
  -d '{"action":"evaluate","args":{"code":"(() => { const items = [...document.querySelectorAll(\"[data-e2e=user-post-item]\")].slice(0, 10); return items.map((item, i) => { const link = item.querySelector(\"a\"); const views = item.querySelector(\"[data-e2e=video-views]\"); return { index: i, url: link ? link.href : null, title: item.innerText.slice(0, 100), views: views ? views.innerText : null, raw_text: item.innerText.slice(0, 300) }; }); })()"},"session":"tiktok-creator"}'
```

## 输出目录结构

```text
bggg-tiktok-search/projects/tiktok-research/YYYYMMDD_HHMMSS_<slug>/
├── collected_items.json
├── research_notes.md
└── screenshots/
    ├── search_001.png
    ├── search_002.png
    └── ...
```

### collected_items.json 结构

```json
{
  "method": "kimi-webbridge",
  "query": "skincare routine",
  "source_url": "https://www.tiktok.com/search?q=skincare%20routine",
  "session": "tiktok-search",
  "items": [
    {
      "url": "https://www.tiktok.com/@creator/video/1234567890123456789",
      "author": "@creator",
      "author_url": "https://www.tiktok.com/@creator",
      "title": "visible caption or card text",
      "metric_1": "visible metric",
      "metric_2": "visible metric",
      "date": "visible date",
      "raw_text": "short visible evidence",
      "screenshot": "screenshots/search_001.png",
      "notes": "why this item matters"
    }
  ]
}
```

## 调研输出建议

最终回复用户时优先给：

1. 调研包路径：JSON、CSV、Markdown、截图。
2. 最高价值候选视频或博主列表。
3. 内容结构洞察：选题、开头钩子、账号定位、带货意图、镜头/话术模式。
4. 下一步建议：是否进入下载、转写、深度拆解或飞书多维表格沉淀。

## 注意事项

- **TikTok DOM 经常变化**，`evaluate` 里的 selector 需要按实际页面结构调整。先用 `snapshot` 确认当前结构再写提取逻辑。
- **遇到登录、风控、地区限制或验证码**，让用户在真实 Chrome 里手动处理后继续。不要代解 CAPTCHA。
- **不做点赞、关注、评论、发私信、发帖、改账号设置**等外部副作用动作；如果用户明确要求，动作前必须确认。
- 不要提交 Cookie、浏览器 profile、截图、CSV、JSON 采集结果或任何运行产物到公开仓库。
- 截图文件写到 `projects/tiktok-research/.../screenshots/`；不要把 base64 截图直接贴进上下文。
- **任务结束后关闭 session**：
  ```bash
  curl -s -X POST "$WEBBRIDGE_URL/command" \
    -d '{"action":"close_session","session":"tiktok-search"}'
  ```
- `references/implementation-notes.md` 记录了从其他 browser-use skill 学到的设计模式；第三方参考项目不随本 skill vendored。

更多实现细节按需读取 [references/implementation-notes.md](references/implementation-notes.md)。
