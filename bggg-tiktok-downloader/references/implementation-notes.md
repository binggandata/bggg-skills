# Implementation Notes

## Dependencies

- yt-dlp: 用于单视频和博主批量下载。
- ffmpeg: 由 yt-dlp 合并音视频时使用。
- TikTokDownloader: 可选。设置 `TIKTOKDOWNLOADER_ROOT` 或 `--tiktokdownloader-root` 时，只用于借用链接类型识别规则。

## 下载策略

脚本会先尝试加载 TikTokDownloader 的 `ExtractorTikTok` 正则辅助判断链接类型；如果没有配置该仓库或依赖未安装，脚本会退回内置正则。

下载命令使用这些核心参数：

- `--download-archive` 记录已下载作品，重复运行会跳过。
- `--merge-output-format mp4` 尽量落地为 mp4。
- `--format bestvideo.../best` 优先拿 H.264/mp4，便于后续本地播放和 whisper 转写。
- `--playlist-end N` 用于博主指定数量；`N=0` 时不加该参数，表示全部可见作品。

单视频兜底：

- 当 `yt-dlp` 不存在或没有产出文件时，请求 `https://www.tikwm.com/api/`。
- 兜底只用于单个视频，不用于博主全量下载。

## 输出

默认输出目录：

`projects/downloads/tiktok` under this skill directory.

每次运行会写：

- `.bggg-tiktok-download-archive.txt`
- `download_manifest.json`
- 可选 `.info.json` 和封面图
