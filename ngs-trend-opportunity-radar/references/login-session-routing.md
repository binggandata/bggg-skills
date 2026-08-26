# 采集登录态选择

登录态是业务卡确认后的条件式执行闸门，不是业务卡第 5 项。Google Trends 和 TikTok 优先使用用户选定的已登录浏览器环境；Reddit API 受阻后使用用户确认的 `old.reddit.com` 登录环境；Sorftime 与 Amazon 评论采集不依赖该浏览器登录态。

## 何时询问

开始外部采集前，以只读方式检查当前可用的浏览器窗口、标签页、Chrome profile／CDP 会话或应用内浏览器会话。只记录非敏感标签，不读取 Cookie、Token、本地存储、密码或完整账号资料。

- 没有可用登录环境：Google Trends／TikTok 需要页面时请用户先登录；Reddit 仍可先运行 OAuth／公共 JSON API，只有 API 被阻断后才请求登录 old Reddit。
- 只有 1 个可用环境：回显将使用哪个环境；用户已说“开始”后可继续。
- 有 2 个及以上可用环境：必须先让用户选择，不能替用户猜，也不能把多个账号的数据静默混在一起。

## 多登录态提问模板

```text
【采集登录态】

检测到多个可用登录环境：
A. Chrome／工作资料
B. Chrome／个人资料
C. Codex 应用内浏览器

请选择：
- 全部平台使用 A；或
- Google Trends：A｜TikTok：C｜Reddit old：A
```

只显示足以让用户区分的浏览器、profile、窗口或当前可见账号昵称。不要回显邮箱、手机号、Cookie 值、Token 或本地 profile 绝对路径。若工具无法可靠识别账号，只显示“Chrome 窗口 1／窗口 2 + 当前平台标签页”，让用户选择。

## 落盘字段

在 `00-research-brief/research_brief.json` 保存非敏感路由信息：

```json
{
  "login_session_candidates": [
    {"session_id": "browser-1", "label": "Chrome 工作资料", "visible_platforms": ["Google Trends", "TikTok", "old Reddit"]}
  ],
  "login_session_selection": {
    "mode": "single",
    "session_id": "browser-1"
  }
}
```

按平台分配时使用：

```json
{
  "login_session_selection": {
    "mode": "per_source",
    "mapping": {
      "google_trends": "browser-1",
      "tiktok": "browser-2",
      "reddit_old": "browser-1"
    }
  }
}
```

这里的 `session_id` 只是本次运行的临时标签，不是凭证。报告只披露“使用用户确认的登录环境”，不公开账号身份。

## 登录优先与停止规则

1. 用户已选择登录环境时，Google Trends、TikTok 直接走该环境。Reddit 仍先走结构化 API；受阻时切到该环境中的 `old.reddit.com`。
2. 如果 Reddit API 返回 403、非 JSON、challenge 或网络安全拦截，切到用户选定的 old Reddit 后最多重试 1 次 `.json`；仍被 `ERR_BLOCKED_BY_CLIENT` 时可采普通评论页的可见 DOM。
3. 选定环境仍被阻断时，保存失败日志并降级；不循环重试，不绕过验证码或挑战页。
4. 登录过期、页面跳到其他账号或需要切换环境时停止询问用户；不得静默换号。
5. 除非用户明确按平台分配，否则同一平台整个运行只使用一个登录环境，避免样本因账号推荐差异混杂。
