---
name: bggg-tiktok-downloader
description: >
  下载 TikTok 视频到本地。当用户给出 TikTok 单个视频链接、分享链接、视频链接文本、
  TikTok 博主主页链接、@handle，并要求下载、保存、抓取、批量下载、下载博主作品、
  下载指定数量或下载全部作品时，使用此 skill。优先用 yt-dlp，单视频下载失败时用 tikwm 兜底；
  可选引用本地 TikTokDownloader 作为链接类型识别辅助。
---

# BGGG TikTok Downloader

## 目标

把 TikTok 视频下载到本地项目目录。优先使用随 skill 捆绑的确定性脚本：

```bash
python3 bggg-tiktok-downloader/scripts/download_tiktok.py "<TikTok URL>"
```

脚本优先使用 `yt-dlp` 负责单视频和博主列表下载；单视频在 `yt-dlp` 不可用或失败时使用 tikwm 兜底。若设置 `TIKTOKDOWNLOADER_ROOT` 或传 `--tiktokdownloader-root`，脚本会尝试引用本地 `TikTokDownloader` 的链接识别规则；没有该目录也可以运行。

## 工作流

1. 识别输入类型：
   - 包含 `/video/` 或 `/photo/` 的 TikTok 链接按单个作品处理。
   - `https://www.tiktok.com/@username` 这类主页链接按博主处理。
   - 用户指定“下载 N 条/前 N 个/最新 N 个”时传 `--limit N`。
   - 用户说“全部”或只给博主链接且无数量时传 `--limit 0`，表示不限制数量。
2. 选择输出目录。默认是本 skill 下的 `projects/downloads/tiktok`；用户指定目录时传 `--output-dir`。
3. 运行脚本并查看 JSON 输出里的 `manifestPath`、`itemCount` 和 `items[].filePath`。
4. 如果后续要转写音轨，把输出的视频目录交给 `bggg-tiktok-readvideo`。

## 常用命令

下载单个视频：

```bash
python3 bggg-tiktok-downloader/scripts/download_tiktok.py "https://www.tiktok.com/@user/video/1234567890123456789" --thumbnail
```

下载某博主前 30 个视频：

```bash
python3 bggg-tiktok-downloader/scripts/download_tiktok.py "https://www.tiktok.com/@user" --mode author --limit 30 --thumbnail
```

下载某博主全部可见视频：

```bash
python3 bggg-tiktok-downloader/scripts/download_tiktok.py "https://www.tiktok.com/@user" --mode author --limit 0 --thumbnail
```

需要登录态时，可以显式使用浏览器 Cookie：

```bash
python3 bggg-tiktok-downloader/scripts/download_tiktok.py "https://www.tiktok.com/@user" --mode author --limit 20 --cookies-browser chrome
```

## 注意事项

- 只下载用户有权保存和处理的内容。遇到私密账号、地区限制或风控时，需要用户提供可用 Cookie。
- 不要提交 Cookie 文件、浏览器 profile、下载结果、`.info.json` 或采集 manifest 到公开仓库。
- 作者批量下载依赖 `yt-dlp`；单视频可走 tikwm 兜底。
- 输出目录内会生成 `.bggg-tiktok-download-archive.txt` 跳过重复视频，以及 `download_manifest.json` 记录结果。

更多实现细节按需读取 [references/implementation-notes.md](references/implementation-notes.md)。
