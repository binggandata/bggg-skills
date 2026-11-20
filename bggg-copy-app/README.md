# bggg-copy-app

Android App **净室/高保真复刻**方法论 skill：ADB 接管真机 → uiautomator 语义树+截图解析 → 规格化 → 原生/跨端重建 → 同流程逐状态对比与效果级验收（时长/版本归属/计费/通知/失败恢复）→ 证据沉淀与开源交付。

由 FlowClone（Google Flow 净室复刻）项目沉淀，已在真机上完成 L3 级验收。

## 安装

### Codex

```bash
mkdir -p ~/.codex/skills
cp -R bggg-copy-app ~/.codex/skills/
```

或开发时软链接：

```bash
ln -s "$PWD/bggg-copy-app" ~/.codex/skills/bggg-copy-app
```

### DeepSeek Harness

```bash
mkdir -p ~/.agents/skills
cp -R bggg-copy-app ~/.agents/skills/
# 或项目级：<project>/.dsh/skills/bggg-copy-app/
```

## 使用

在会话中直接说“按 bggg-copy-app 复刻这个 App”，或让 Agent 加载 `bggg-copy-app`。入口：`SKILL.md`。

## 内容

- `SKILL.md`：工作流、硬性规则、L0–L5 深度等级、资源索引
- `references/`：接入协议、UI 解析、深度标准、效果级验收、原生重建、30 条踩坑、DSH 并行、交付脱敏、FlowClone 案例
- `templates/`：项目计划、探索日志、UI 差异表、行为审计、验收报告
- `scripts/`：`adb-check.sh`、`ui.py`（uiautomator XML 解析/点击）、`cap.sh`
- `evals/`：示例评测用例

## 许可

MIT。引用 REA / craft-anything 仅作方法论对照，未包含其代码。
