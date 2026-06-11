# bggg-tiktok-downloader

中文 | [English](./README_EN.md)

`bggg-tiktok-downloader` 是一个 TikTok 视频下载 skill。它优先使用 `yt-dlp` 下载单个视频或博主可见作品，单视频失败时用 tikwm 兜底，并输出 `download_manifest.json` 方便后续转写或分析。

## 安装

```bash
mkdir -p ~/.codex/skills
cp -R bggg-tiktok-downloader ~/.codex/skills/
python3 -m pip install -U yt-dlp
brew install ffmpeg
```

可选：如果你本地有 TikTokDownloader，可设置：

```bash
export TIKTOKDOWNLOADER_ROOT="/path/to/TikTokDownloader"
```

它只用于辅助识别链接类型，不是必需依赖。

## 使用

下载单个视频：

```bash
python3 bggg-tiktok-downloader/scripts/download_tiktok.py \
  "https://www.tiktok.com/@user/video/1234567890123456789" \
  --thumbnail
```

下载博主前 30 个作品：

```bash
python3 bggg-tiktok-downloader/scripts/download_tiktok.py \
  "https://www.tiktok.com/@user" \
  --mode author \
  --limit 30 \
  --thumbnail
```

默认输出目录：

```text
bggg-tiktok-downloader/projects/downloads/tiktok/
```

## 安全与合规

只下载你有权保存和处理的内容。需要登录态时可显式传 `--cookies-browser chrome` 或 `--cookies-file`，但不要提交 Cookie 文件、浏览器 profile、下载结果或 `.info.json` 到公开仓库。
