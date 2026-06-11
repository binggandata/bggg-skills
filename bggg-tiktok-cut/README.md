# bggg-tiktok-cut

中文 | [English](./README_EN.md)

`bggg-tiktok-cut` 是一个本地 FFmpeg 短视频剪辑 skill，用于把 AI 视频、口播素材、产品素材或多段视频剪成可发布到 TikTok/Reels/Shorts 的 9:16 成片。

## 能做什么

- 初始化剪辑项目目录，集中管理 raw、metadata、transcripts、plans、captions、renders。
- 用 `ffprobe` 和抽帧生成素材清单。
- 可选转写口播音频。
- 用 JSON edit plan 表达剪辑、重构图、字幕、overlay、BGM 和导出参数。
- 用 FFmpeg 渲染 1080x1920 MP4，并生成渲染报告。

## 安装

```bash
mkdir -p ~/.codex/skills
cp -R bggg-tiktok-cut ~/.codex/skills/
brew install ffmpeg
```

可选安装 Whisper 或 faster-whisper 用于转写。

## 使用

```bash
python3 bggg-tiktok-cut/scripts/init_project.py \
  bggg-tiktok-cut/projects/20260611_demo \
  --name demo \
  --inputs "/path/to/source.mp4"

python3 bggg-tiktok-cut/scripts/probe_media.py \
  bggg-tiktok-cut/projects/20260611_demo/raw \
  --out bggg-tiktok-cut/projects/20260611_demo/metadata/media_inventory.json \
  --frames-dir bggg-tiktok-cut/projects/20260611_demo/diagnostics/frames

python3 bggg-tiktok-cut/scripts/make_plan.py \
  bggg-tiktok-cut/projects/20260611_demo \
  --title "TikTok hook" \
  --target-seconds 30

python3 bggg-tiktok-cut/scripts/render_tiktok_cut.py \
  bggg-tiktok-cut/projects/20260611_demo/plans/edit_plan.json
```

## 注意

运行产物、成片、字幕、转写和诊断帧都应留在 `projects/` 或外部工作目录，不要提交到公开仓库。
