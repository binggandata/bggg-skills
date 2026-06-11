# bggg-tiktok-capcut

中文 | [English](./README_EN.md)

`bggg-tiktok-capcut` 是一个用于 CapCut 草稿生成、模板样式提取和 AI 视频质量检查的 Codex skill。它可以把本地 AI 视频套用已有 CapCut 草稿模板，生成可在 CapCut 首页显示并继续编辑的新草稿，也可以抽帧检查 AI 痕迹并规划修复窗口。

## 能做什么

- 基于已有 CapCut 草稿模板生成新草稿。
- 提取模板中的字幕样式、转场、动画和特效。
- 验证草稿索引、嵌套 timeline 和素材路径是否一致。
- 对视频或 CapCut 草稿抽帧，生成 contact sheet 和 review 模板。
- 根据 review JSON 规划 AI 痕迹修复窗口。
- 调用本地 RIFE 后端做高质量补帧预处理。

## 安装

```bash
mkdir -p ~/.codex/skills
cp -R bggg-tiktok-capcut ~/.codex/skills/
```

默认 CapCut 草稿目录为：

```bash
$HOME/Movies/CapCut/User Data/Projects/com.lveditor.draft
```

如果你的目录不同：

```bash
export CAPCUT_DRAFT_ROOT="/path/to/com.lveditor.draft"
```

## 使用

生成草稿：

```bash
node bggg-tiktok-capcut/scripts/create-capcut-draft.mjs \
  --template "template-draft-name" \
  --video "/path/to/ai-video.mp4" \
  --name "new-draft-name" \
  --captions "Hook\nProof\nCTA"
```

验证草稿：

```bash
node bggg-tiktok-capcut/scripts/validate-capcut-draft.mjs --draft "new-draft-name"
```

抽帧检查：

```bash
node bggg-tiktok-capcut/scripts/extract-ai-artifact-frames.mjs \
  --video "/path/to/ai-video.mp4" \
  --output-root bggg-tiktok-capcut/projects/ai-artifact-qa
```

## 注意

不要提交 CapCut 草稿、视频、截图、补帧中间文件或 review 结果。运行产物请放在 `projects/` 或外部工作目录。
