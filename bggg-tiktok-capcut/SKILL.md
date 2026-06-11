---
name: bggg-tiktok-capcut
description: >
  通用 CapCut 草稿生成与 AI 视频检查 skill。用于把本地 AI 视频套用现有 CapCut 草稿模板，
  生成可在 CapCut 首页显示并可编辑的新草稿；也用于提取模板样式、验证草稿结构、抽帧检查
  AI 痕迹、规划修复窗口和做本地 RIFE 补帧。
---

# BGGG TikTok CapCut

这个 skill 只保留通用能力：

- 基于现有 CapCut 草稿模板生成新草稿
- 提取模板里的字幕样式、转场、动画、特效
- 验证草稿是否会被 CapCut 索引并显示
- 对 AI 视频或 CapCut 草稿抽帧做 AI 痕迹检查
- 为明显 AI 痕迹生成修复窗口
- 用本地 RIFE 做高质量补帧预处理

默认 CapCut 草稿根目录：

```bash
$HOME/Movies/CapCut/User Data/Projects/com.lveditor.draft
```

如果你的 CapCut 草稿目录不同，设置 `CAPCUT_DRAFT_ROOT` 或给脚本传 `--output-dir` / `--draft-root`。

## 生成草稿

```bash
node <skill-dir>/scripts/create-capcut-draft.mjs \
  --template "PL-magicrep-PV-001" \
  --video "/path/to/ai-video.mp4" \
  --name "ai-video-capcut-001" \
  --captions "Line 1\nLine 2\nLine 3" \
  --split-at 7.5
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--template` | 已存在的 CapCut 草稿目录名 |
| `--video` | 本地 AI 视频路径 |
| `--name` | 新草稿目录名和首页显示名 |
| `--captions` | 字幕文本，可用 `\n` 分行 |
| `--srt` | SRT 字幕文件，替代 `--captions` |
| `--split-at` | 视频切分点，转场会挂在切点前一段 |
| `--no-transition` | 不复制模板转场 |
| `--no-captions` | 不生成字幕轨道 |
| `--output-dir` | 自定义 CapCut 草稿根目录 |
| `--force` | 同名草稿已存在时先替换 |

脚本会同步这些 CapCut 会读取的文件，避免草稿目录存在但首页不显示：

- `draft_info.json`
- `draft_meta_info.json`
- `draft_info.json.bak`
- `template-2.tmp`
- `Timelines/project.json`
- `Timelines/<draft_info.id>/draft_info.json`
- `Timelines/<draft_info.id>/template.tmp`
- `Timelines/<draft_info.id>/template-2.tmp`
- `root_meta_info.json`

生成后如果 CapCut 已打开，完全退出再打开，让首页重新加载 `root_meta_info.json`。

## 验证草稿

```bash
node <skill-dir>/scripts/validate-capcut-draft.mjs \
  --draft "ai-video-capcut-001" \
  --stale-marker "OLD_TEMPLATE_NAME"
```

验证点包括：

- root 索引是否有对应条目
- `draft_info.id` 与 `Timelines/<id>`、`project.json` 是否一致
- 顶层和嵌套 `draft_info/template` 副本是否同步
- 视频素材路径是否存在
- 是否有旧模板名或旧素材路径残留

## 提取模板样式

```bash
node <skill-dir>/scripts/extract-template-styles.mjs \
  --template "PL-magicrep-PV-001" \
  --output ./capcut-template-styles.json
```

输出包含字幕样式、转场、动画、特效、画布和轨道结构。

## AI 痕迹检查

对单个视频抽帧：

```bash
node <skill-dir>/scripts/extract-ai-artifact-frames.mjs \
  --video "/path/to/ai-video.mp4" \
  --output-root ./ai-artifact-qa
```

对 CapCut 草稿时间线抽帧：

```bash
node <skill-dir>/scripts/extract-ai-artifact-frames.mjs \
  --draft "ai-video-capcut-001" \
  --output-root ./ai-artifact-qa
```

批量检查本地目录：

```bash
node <skill-dir>/scripts/extract-ai-artifact-frames.mjs \
  --video-dir "/path/to/videos" \
  --output-root ./ai-artifact-qa
```

阅读 `references/ai-artifact-qa.md` 获取判定标准和 review JSON 结构。

## 修复规划

```bash
node <skill-dir>/scripts/plan-ai-artifact-fixes.mjs \
  --review ./ai_artifact_review.json \
  --output ./ai_artifact_fix_plan.json
```

## RIFE 补帧

阅读 `references/smart-frame-interpolation.md`。常用命令：

```bash
node <skill-dir>/scripts/smart-frame-interpolate.mjs \
  --input "/path/to/source.mp4" \
  --output "/path/to/source_60fps_rife.mp4"
```

## 故障排查

先运行：

```bash
node <skill-dir>/scripts/validate-capcut-draft.mjs --draft "<draft-name>"
```

常见问题见 `references/failure-modes.md`。

## 脚本清单

| 脚本 | 用途 |
| --- | --- |
| `scripts/create-capcut-draft.mjs` | 基于模板生成可显示的 CapCut 草稿 |
| `scripts/validate-capcut-draft.mjs` | 验证单个草稿结构和索引 |
| `scripts/extract-template-styles.mjs` | 提取模板样式 |
| `scripts/extract-ai-artifact-frames.mjs` | 对视频/草稿抽帧生成 contact sheet |
| `scripts/plan-ai-artifact-fixes.mjs` | 根据 review JSON 规划修复窗口 |
| `scripts/smart-frame-interpolate.mjs` | 本地 RIFE 补帧 |
