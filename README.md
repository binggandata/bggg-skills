# bggg-skills

中文 | [English](./README_EN.md)

`bggg-skills` 是 BGGG 开源的 Codex Skills 集合仓库。

每个 skill 都是一个独立目录，可以复制或软链接到 `~/.codex/skills/` 使用。后续更多 BGGG 的可复用工作流、工具封装和创作能力都会逐步放到这个仓库里。

Created by [@binggandata](https://github.com/binggandata) · [小红书](https://xhslink.com/m/4ndptyfq4vu) · [X / Twitter](https://x.com/bggg_ai) · 微信：binggandata2

## 当前 Skills

- [`bggg-creator-image2psd`](./bggg-creator-image2psd)：把一张或多张图片转成可编辑的分层 PSD，支持 Codex/imagegen 辅助拆图、全画布 PNG 图层导出、颜色拆层、白底转透明，以及纯 Python PSD 写入。
- [`bggg-creator-image2ppt`](./bggg-creator-image2ppt)：把图片、截图、HTML 或 SVG 设计稿转成可编辑 PPTX，支持 Codex/imagegen 辅助组件重建、文本框还原、原生形状重建，以及 HTML/SVG 解析到 PPTX。
- [`bggg-skill-taotie`](./bggg-skill-taotie)：Skill 进化器，通过对比、分析和吸收其他 skill 的优势，帮助目标 skill 渐进式升级。
- [`bggg-tiktok-search`](./bggg-tiktok-search)：复用本地真实 Chrome 登录态做 TikTok 只读调研，输出 JSON/CSV/Markdown 和截图证据。
- [`bggg-tiktok-downloader`](./bggg-tiktok-downloader)：用 `yt-dlp` 下载 TikTok 单视频或博主可见作品，单视频失败时用 tikwm 兜底。
- [`bggg-tiktok-readvideo`](./bggg-tiktok-readvideo)：把 TikTok/UGC/本地视频拆成 Codex 可读的 metadata、transcript、scene、keyframe、contact sheet 和 timeline。
- [`bggg-tiktok-cut`](./bggg-tiktok-cut)：用 JSON edit plan 和 FFmpeg 把 AI 视频、本地素材或口播素材剪成 9:16 TikTok 成片。
- [`bggg-tiktok-capcut`](./bggg-tiktok-capcut)：基于已有 CapCut 模板草稿生成新草稿，提取模板样式，验证草稿结构，并检查 AI 视频痕迹。
- [`bggg-tiktok-seedance`](./bggg-tiktok-seedance)：通过用户配置的 Seedance Gateway 做单条或批量并发视频生成，支持参考媒体和虚拟资产。

## 安装

克隆仓库：

```bash
git clone https://github.com/binggandata/bggg-skills.git
cd bggg-skills
```

复制某个 skill 到 Codex：

```bash
mkdir -p ~/.codex/skills
cp -R bggg-creator-image2psd ~/.codex/skills/
cp -R bggg-creator-image2ppt ~/.codex/skills/
cp -R bggg-tiktok-readvideo ~/.codex/skills/
```

开发时也可以用软链接：

```bash
ln -s "$PWD/bggg-creator-image2psd" ~/.codex/skills/bggg-creator-image2psd
ln -s "$PWD/bggg-creator-image2ppt" ~/.codex/skills/bggg-creator-image2ppt
ln -s "$PWD/bggg-tiktok-readvideo" ~/.codex/skills/bggg-tiktok-readvideo
```

如果 skill 目录下有 `scripts/requirements.txt`，再安装它的依赖：

```bash
python3 -m pip install -r ~/.codex/skills/bggg-creator-image2psd/scripts/requirements.txt
python3 -m pip install -r ~/.codex/skills/bggg-creator-image2ppt/scripts/requirements.txt
```

## 仓库结构

```text
bggg-skills/
├── README.md
├── README_EN.md
├── LICENSE
├── bggg-creator-image2psd/
│   ├── SKILL.md
│   ├── README.md
│   ├── README_EN.md
│   ├── scripts/
│   ├── references/
│   ├── assets/
│   ├── evals/
│   └── projects/
├── bggg-creator-image2ppt/
│   ├── SKILL.md
│   ├── README.md
│   ├── README_EN.md
│   ├── scripts/
│   ├── references/
│   ├── assets/
│   ├── evals/
│   └── projects/
├── bggg-skill-taotie/
│   ├── SKILL.md
│   ├── README.md
│   ├── INSTALL.md
│   ├── references/
│   └── evals/
├── bggg-tiktok-search/
├── bggg-tiktok-downloader/
├── bggg-tiktok-readvideo/
├── bggg-tiktok-cut/
├── bggg-tiktok-capcut/
└── bggg-tiktok-seedance/
```

`projects/` 是 skill 运行时的本地项目输出目录。开源仓库只保留 `.gitkeep`，不会提交实际生成的图片、PSD、zip 或过程文件。
TikTok 系列还会忽略下载视频、截图、CSV/JSON 调研包、字幕、转写、CapCut 草稿和 Seedance 生成结果。

## 贡献新 Skill

推荐每个 skill 使用下面的基本结构：

```text
skill-name/
├── SKILL.md
├── README.md
├── README_EN.md
├── scripts/
├── references/
├── assets/
├── evals/
└── projects/.gitkeep
```

其中：

- `SKILL.md` 给 Codex 读取，用于触发和执行。
- `README.md` 是中文主说明，给用户阅读。
- `README_EN.md` 是英文说明。
- `scripts/` 放确定性脚本。
- `references/` 放按需读取的参考材料。
- `projects/` 放运行产物，默认不提交。

## License

MIT
