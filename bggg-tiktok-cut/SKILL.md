---
name: bggg-tiktok-cut
description: >
  用于把 AI 生成的视频、本地素材、口播素材或产品短片剪成可发布到 TikTok 的竖屏成片。
  当用户要求剪短视频、TikTok/Reels/Shorts 版本、9:16 重构图、批量短视频剪辑、AI 视频二创、
  加大字字幕、BGM、音频 ducking、hook overlay、去空白、粗剪、导出 final.mp4 或根据素材文件夹
  生成可发布短视频时，应使用此 skill。适合本地 FFmpeg/Whisper/Codex 工作流。
compatibility: "Requires Python 3, ffmpeg and ffprobe. Optional: faster-whisper or whisper CLI for transcription, auto-editor for silence removal."
---

# BGGG TikTok Cut

把 AI 生成的视频剪成 TikTok 可发布的 9:16 成片。Codex 负责判断故事、节奏、画面瑕疵和字幕文案；脚本负责可重复的 FFmpeg 渲染。

## 快速流程

1. **定位输入**：确认视频文件、素材文件夹、BGM、字幕/SRT、产品卖点或脚本。用户没有给完整参数时，先按 TikTok 默认值推进：1080x1920、30fps、15-45 秒、前 1-3 秒强 hook、大字字幕、轻 BGM。
2. **建项目**：把本次产物收进一个项目目录，避免散落在工作区。
   ```bash
   python3 <skill-dir>/scripts/init_project.py "<project-dir>" --name "<name>" --inputs "<video1>" "<video2>"
   ```
3. **探测素材**：生成 media inventory 和抽帧，用抽帧判断 AI 视频的坏帧、主体位置、适合 cover 还是 blur-bg。
   ```bash
   python3 <skill-dir>/scripts/probe_media.py "<project-dir>/raw" --out "<project-dir>/metadata/media_inventory.json" --frames-dir "<project-dir>/diagnostics/frames"
   ```
4. **需要语音时转写**：有口播/旁白时生成 JSON/SRT；无语音的 AI 视频可直接根据脚本写 captions/overlays。
   ```bash
   python3 <skill-dir>/scripts/transcribe.py "<project-dir>/raw/source.mp4" --out-dir "<project-dir>/transcripts" --model small --language auto
   ```
5. **写剪辑计划**：编辑 `plans/edit_plan.template.json`，或先生成 starter plan 再修改。
   ```bash
   python3 <skill-dir>/scripts/make_plan.py "<project-dir>" --title "<hook>" --target-seconds 30
   ```
6. **渲染**：
   ```bash
   python3 <skill-dir>/scripts/render_tiktok_cut.py "<project-dir>/plans/edit_plan.json"
   ```
7. **自检**：用 `ffprobe` 验证输出尺寸、时长、音频；抽查开头、字幕密集处、结尾。如果字幕被 TikTok UI 安全区遮挡、画面主体被裁掉、音频爆音或 BGM 过响，改 plan 后重渲染。

## 剪辑判断

- **AI 视频优先看画面连续性**：删掉变形手、漂移 logo、字幕穿帮、闪帧、明显循环卡顿和主体出框的片段。
- **前 3 秒要给理由**：用画面强动作、结果预览、反差句、价格/痛点/卖点 overlay 之一开场。不要用慢慢铺垫。
- **竖屏重构图默认 `blur-bg`**：横屏或宽画幅 AI 视频用模糊背景保留完整主体；主体稳定且足够大时用 `cover`；需要展示全图时用 `contain`。
- **字幕安全区**：字幕默认放在中下区域，避开 TikTok 底部描述区和右侧操作栏。价格、优惠、CTA 放顶部或中部 badge。
- **BGM 是辅助**：有口播时 BGM 轻铺，默认 0.08-0.14；无口播的视觉向视频可提高到 0.18-0.28，但避免压过关键音效。
- **批量剪辑**：每条视频单独建项目或在同一项目中保存多个 `plans/*.json`，输出命名带产品/角度/序号。

## Edit Plan

渲染脚本读取 JSON plan。需要详细字段时读 `references/edit-plan-schema.md`。

最小可用示例：

```json
{
  "version": 1,
  "project": {
    "title": "TikTok cut",
    "platform": "tiktok",
    "target": {"width": 1080, "height": 1920, "fps": 30}
  },
  "settings": {
    "fit": "blur-bg",
    "grade": "punch",
    "caption_style": "tiktok-bold",
    "voice_volume": 1.0,
    "output_name": "final_tiktok.mp4"
  },
  "clips": [
    {"source": "raw/clip.mp4", "start": 0.0, "end": 6.2, "fit": "blur-bg", "label": "HOOK"}
  ],
  "captions": [
    {"start": 0.0, "end": 2.4, "text": "第一眼就要看到结果", "style": "hook"}
  ],
  "overlays": [
    {"start": 0.0, "end": 2.4, "text": "AI 视频二创", "style": "hook"}
  ],
  "bgm": {"path": "assets/bgm/music.mp3", "volume": 0.12},
  "export": {"crf": 20, "preset": "fast"}
}
```

## 脚本职责

- `scripts/init_project.py`：创建项目结构，复制输入，写 plan 模板和 manifest。
- `scripts/probe_media.py`：ffprobe 素材并抽帧。
- `scripts/transcribe.py`：可选本地转写，优先 faster-whisper，回退 whisper CLI。
- `scripts/make_plan.py`：从 `raw/` 生成保守 starter plan。
- `scripts/render_tiktok_cut.py`：按 plan 标准化片段、拼接、加字幕/overlay/watermark、混 BGM、导出 TikTok MP4。

## 参考资料

- 需要剪辑策略时读 `references/tiktok-editing-playbook.md`。
- 需要修改 JSON 字段时读 `references/edit-plan-schema.md`。
- 需要理解参考项目取舍时读 `references/source-projects.md`。
- 第三方参考仓库不随本 skill vendored；`references/source-projects.md` 只记录学习到的设计模式和可回溯来源。

## 交付格式

完成后给用户这些路径：

- 成片：`<project-dir>/renders/final_tiktok.mp4`
- 剪辑计划：`<project-dir>/plans/edit_plan.json`
- 渲染报告：`<project-dir>/renders/render_report.json`
- 字幕：`<project-dir>/captions/final_captions.ass`，如果生成了转写，也给 SRT/JSON 路径

如果有未自动解决的问题，明确写成短清单：例如某段 AI 画面有不可修复变形、没有安装 Whisper、BGM 缺失、用户需人工确认品牌合规文案。
