# bggg-tiktok-readvideo

中文 | [English](./README_EN.md)

`bggg-tiktok-readvideo` 是一个让 Codex 读懂视频的本地 skill。它不会让 Codex 直接“看 mp4”，而是把 TikTok/短视频/UGC 素材拆成结构化上下文：元数据、字幕、镜头、关键帧、九宫格总览、音频事件、OCR 和 timeline，让 Codex 可以搜索、引用时间戳、制定剪辑方案，并用 FFmpeg 渲染 9:16 成片。

## 能做什么

- 读取本地 `.mp4/.mov/.webm/.mkv` 视频。
- 用 `ffprobe` 生成 `metadata.json`。
- 用 `ffmpeg` 检测镜头切换并抽关键帧。
- 生成带时间戳标签的 `keyframes/` 和 `contact_sheet.jpg`。
- 可选用本地 `whisper-cli`/`whisper-cpp` 输出 `transcript.txt` 与 `transcript.srt`。
- 对视频/音频文件夹做独立批量转写，输出 `transcripts/` 与 `transcription_manifest.json`。
- 可选用 `tesseract` 对关键帧 OCR。
- 生成给 Codex 阅读的 `timeline.md` 和 `analysis_manifest.json`。
- 根据 `edit_plan.json` 渲染 TikTok 9:16 视频。

## 安装

复制到 Codex skills 目录：

```bash
mkdir -p ~/.codex/skills
cp -R bggg-tiktok-readvideo ~/.codex/skills/
```

开发时可使用软链接：

```bash
ln -s "$PWD/bggg-tiktok-readvideo" ~/.codex/skills/bggg-tiktok-readvideo
```

系统依赖：

```bash
brew install ffmpeg
```

可选依赖：

```bash
brew install whisper-cpp tesseract
```

如果已安装本地 Whisper 模型，脚本会自动查找常见用户级模型目录。也可以用 `--model /path/to/ggml-small.bin` 指定。

## 使用

分析视频：

```bash
python3 bggg-tiktok-readvideo/scripts/analyze_video.py "/path/to/input.mp4" \
  --slug product_qc_ugc
```

只转写音轨：

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/video-or-folder" --recursive --srt
```

输出目录：

```text
bggg-tiktok-readvideo/projects/YYYYMMDD_product_qc_ugc/
├── raw/input.mp4
├── analysis/
│   ├── metadata.json
│   ├── transcript.txt
│   ├── transcript.srt
│   ├── scenes.json
│   ├── timeline.md
│   ├── contact_sheet.jpg
│   ├── keyframes/
│   ├── audio_events.json
│   ├── ocr.json
│   └── analysis_manifest.json
└── output/
    └── edit_plan.template.json
```

让 Codex 读：

```text
Use bggg-tiktok-readvideo to analyze this video. Read timeline.md,
scenes.json, transcript.srt, and contact_sheet.jpg. Find the best TikTok
hook, proof shots, and CTA, then create output/edit_plan.json.
```

渲染：

```bash
python3 bggg-tiktok-readvideo/scripts/render_tiktok.py \
  bggg-tiktok-readvideo/projects/YYYYMMDD_product_qc_ugc/output/edit_plan.json
```

## 批量转写

`bggg-tiktok-whisper` 的独立转写能力已经合并进本 skill。需要 ASR/字幕但不需要关键帧和 timeline 时，直接使用：

```bash
python3 bggg-tiktok-readvideo/scripts/transcribe_video.py "/path/to/downloads" --recursive
```

默认输出在每个源文件旁边的 `transcripts/` 目录；传 `--output-dir` 可集中保存。已存在 `.txt` 时默认跳过，需要重跑时加 `--force`。支持 `--model small`、`--language auto`、`--srt` 和 `--json`。

## 参考项目

设计时学习过这些视频理解项目：

- Popcorn
- video-understanding-engine
- video-understanding-local
- video-analyzer

这些项目不随开源 skill vendored，也不是运行时依赖。运行逻辑已复制/改造成当前 skill 的独立脚本，详细取舍见 `references/source-projects.md`。

## License

MIT
