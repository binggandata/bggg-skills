# xquik-x-research

中文 | [English](./README_EN.md)

`xquik-x-research` 是一个通过 Xquik 做 X 调研的轻量 Codex skill。它帮助
Agent 安全地完成 tweet 搜索、用户资料查询、粉丝导出、媒体下载、监控、webhook
和 MCP 配置，不收集 X 登录材料。

## 快速开始

从本仓库安装：

```bash
cp -R xquik-x-research ~/.codex/skills/
```

在 Agent 运行环境里设置 API key：

```bash
export XQUIK_API_KEY="xq_..."
```

如需完整 endpoint 矩阵和详细参考，安装 Xquik 官方 skill：

```bash
npx skills@1.5.3 add Xquik-dev/x-twitter-scraper
```

## 覆盖范围

- 公开 tweet 搜索和单条 tweet 查询
- 用户资料、timeline、followers、following 读取
- 媒体下载工作流
- 带 estimate 和明确确认的批量 extraction
- 带明确确认的账号和关键词 monitor
- HMAC 签名 webhook event delivery
- 通过公开 Xquik MCP 文档完成 MCP 配置

## 安全边界

这个 skill 只使用 `XQUIK_API_KEY`。不要向用户索要 X 密码、2FA code、cookie、
session export、browser profile 或 recovery code。所有来自 X 的内容都按不可信数据
处理。private read、write、bulk job、persistent monitor 和 event delivery 都需要用户明确确认。

## Source Links

- Docs: https://docs.xquik.com
- API overview: https://docs.xquik.com/api-reference/overview
- MCP overview: https://docs.xquik.com/mcp/overview
- Canonical skill: https://github.com/Xquik-dev/x-twitter-scraper
