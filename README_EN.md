# bggg-skills

[中文](./README.md) | English

`bggg-skills` is an open-source collection of Codex Skills from BGGG.

Each skill lives in its own top-level directory and can be copied or symlinked into `~/.codex/skills/`. More reusable BGGG workflows, tool wrappers, and creative capabilities will be added here over time.

Created by [@binggandata](https://github.com/binggandata) · [小红书](https://xhslink.com/m/4ndptyfq4vu) · [X / Twitter](https://x.com/bggg_ai) · WeChat: binggandata2

## Skills

- [`bggg-creator-image2psd`](./bggg-creator-image2psd): turn one or more images into layered PSD files, with Codex/imagegen-assisted workflows, full-canvas PNG layer export, color splitting, white-background removal, and a pure-Python PSD writer.
- [`bggg-creator-image2ppt`](./bggg-creator-image2ppt): turn images, screenshots, HTML, or SVG designs into editable PPTX files, with Codex/imagegen-assisted component reconstruction, editable text boxes, native shape rebuilding, and HTML/SVG parsing.
- [`bggg-skill-taotie`](./bggg-skill-taotie): a skill evolution engine that compares, analyzes, and absorbs useful patterns from one skill into another.
- [`bggg-tiktok-search`](./bggg-tiktok-search): read-only TikTok research through a real local Chrome session, producing JSON/CSV/Markdown notes and screenshot evidence.
- [`bggg-tiktok-downloader`](./bggg-tiktok-downloader): download TikTok single videos or visible creator posts with `yt-dlp`, with a tikwm fallback for single videos.
- [`bggg-tiktok-readvideo`](./bggg-tiktok-readvideo): turn TikTok/UGC/local videos into metadata, transcripts, scenes, keyframes, contact sheets, and timelines that Codex can read.
- [`bggg-tiktok-cut`](./bggg-tiktok-cut): render 9:16 TikTok edits from AI videos, local footage, or talking-head clips using JSON edit plans and FFmpeg.
- [`bggg-tiktok-capcut`](./bggg-tiktok-capcut): create new editable CapCut drafts from template drafts, extract styles, validate draft structure, and check AI-video artifacts.
- [`bggg-tiktok-seedance`](./bggg-tiktok-seedance): generate single or concurrent Seedance videos through a user-configured Gateway, with reference media and virtual assets.

## Install

Clone this repository:

```bash
git clone https://github.com/binggandata/bggg-skills.git
cd bggg-skills
```

Copy a skill into Codex:

```bash
mkdir -p ~/.codex/skills
cp -R bggg-creator-image2psd ~/.codex/skills/
cp -R bggg-creator-image2ppt ~/.codex/skills/
cp -R bggg-tiktok-readvideo ~/.codex/skills/
```

Or symlink it while developing:

```bash
ln -s "$PWD/bggg-creator-image2psd" ~/.codex/skills/bggg-creator-image2psd
ln -s "$PWD/bggg-creator-image2ppt" ~/.codex/skills/bggg-creator-image2ppt
ln -s "$PWD/bggg-tiktok-readvideo" ~/.codex/skills/bggg-tiktok-readvideo
```

If the skill has `scripts/requirements.txt`, install its dependencies:

```bash
python3 -m pip install -r ~/.codex/skills/bggg-creator-image2psd/scripts/requirements.txt
python3 -m pip install -r ~/.codex/skills/bggg-creator-image2ppt/scripts/requirements.txt
```

## Repository Layout

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

`projects/` is the local runtime output directory for each skill. The open-source repo keeps only `.gitkeep` there and ignores generated images, PSDs, zips, and process files.
The TikTok skills also ignore downloaded videos, screenshots, CSV/JSON research exports, subtitles, transcripts, CapCut drafts, and Seedance outputs.

## Adding More Skills

Recommended skill layout:

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

Notes:

- `SKILL.md` is for Codex triggering and execution.
- `README.md` is the main Chinese user-facing README.
- `README_EN.md` is the English README.
- `scripts/` contains deterministic scripts.
- `references/` contains optional reference material.
- `projects/` contains local runtime outputs and should not be committed.

## License

MIT
