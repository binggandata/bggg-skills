---
name: bggg-tiktok-seedance
description: >
  通过用户配置的 Seedance Gateway 调用 Seedance/Seedance 2.0 生成 TikTok、UGC、
  个护功效类视频。当用户要求 seedance 生视频、参考视频和参考图生成视频、批量并发生成、
  处理真人人物安全报错后重试、检查 Seedance 输出时使用。
  支持直接上传本地图片/视频作为参考素材，支持引用虚拟资产(asset://)。
  批量任务默认支持并发。
---

# BGGG TikTok Seedance

这个 skill 负责通过兼容的 Seedance Gateway 生成视频。核心目标是：可复用、可并发、可恢复、可检查。

## Gateway 信息

使用前必须配置 Gateway 地址，不能依赖仓库里的私有默认值：

```bash
export SEEDANCE_GATEWAY_URL="https://your-seedance-gateway.example.com"
```

如果网关需要认证，使用部署方提供的环境变量或反向代理认证方式；不要把 token、cookie、API key 写进 skill 文件或提交到仓库。

## 核心 API Endpoints

| Endpoint | Method | 用途 |
|----------|--------|------|
| `/apps/api/seedance/tasks` | POST | 创建视频生成任务 (multipart/form-data) |
| `/apps/api/tasks/{task_id}` | GET | 查询任务状态 |
| `/apps/api/seedance/settings` | GET | 获取默认设置 |
| `/apps/api/seedance/virtual-assets` | GET | 列出虚拟资产 |
| `/apps/api/seedance/virtual-assets` | POST | 创建虚拟资产 |

## 默认生成参数

从 Gateway 获取的默认设置：

| 参数 | 默认值 | 可选值 |
|------|--------|--------|
| 模型 | 网关默认 | `seedance-fast`, `seedance2.0` 或网关支持的模型名 |
| 比例 | `9:16` | `16:9`, `1:1`, `9:16` |
| 时长 | `5` 秒 | 5, 10, 15, 20, 30... |
| 分辨率 | 自动 | `480p`, `720p`, `1080p` |
| 水印 | `false` | `true` / `false` |
| 生成音频 | `true` | `true` / `false` |

## 快速开始

### 单条视频生成

```bash
node <skill-dir>/scripts/generate_seedance.mjs \
  --prompt "A woman demonstrating a skincare routine with a green cleansing oil" \
  --output ./projects/seedance-output.mp4 \
  --duration 10 \
  --ratio 9:16
```

带参考图片：

```bash
node <skill-dir>/scripts/generate_seedance.mjs \
  --prompt "参考图片中的护肤流程，展示卸妆油使用过程" \
  --image ~/Downloads/ref1.jpg \
  --image ~/Downloads/ref2.jpg \
  --output ./projects/seedance-output.mp4 \
  --duration 15
```

带参考视频：

```bash
node <skill-dir>/scripts/generate_seedance.mjs \
  --prompt "模仿参考视频的动作和运镜，展示产品使用" \
  --video ~/Downloads/ref-video.mp4 \
  --output ./projects/seedance-output.mp4 \
  --duration 10
```

引用虚拟资产（真人素材）：

```bash
node <skill-dir>/scripts/generate_seedance.mjs \
  --prompt "使用虚拟资产中的人物展示护肤流程" \
  --asset asset://asset-20260610144008-vt4jf \
  --output ./projects/seedance-output.mp4 \
  --duration 10
```

### 批量并发生成

使用配置文件：

```bash
node <skill-dir>/scripts/run_seedance_parallel.mjs \
  --config ./batch-jobs.json \
  --concurrency 3 \
  --skip-existing
```

`batch-jobs.json` 格式：

```json
[
  {
    "prompt": "Morning skincare routine with foam cleanser",
    "images": ["./refs/cleanser.jpg"],
    "output": "./projects/seedance-outputs/video1.mp4",
    "duration": 10,
    "ratio": "9:16"
  },
  {
    "prompt": "Double cleansing demonstration with oil and foam",
    "assets": ["asset://asset-xxx"],
    "output": "./projects/seedance-outputs/video2.mp4",
    "duration": 15,
    "model": "seedance2.0"
  }
]
```

使用 prompts 目录：

```bash
node <skill-dir>/scripts/run_seedance_parallel.mjs \
  --prompts-dir ./prompts/ \
  --images-dir ./images/ \
  --output-dir ./projects/seedance-outputs/ \
  --concurrency 3
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SEEDANCE_GATEWAY_URL` | Gateway 地址 | 必填，或传 `--gateway-url` |
| `SEEDANCE_MODEL` | 默认模型 | `seedance-fast` |
| `SEEDANCE_RATIO` | 默认比例 | `9:16` |
| `SEEDANCE_DURATION` | 默认时长(秒) | `5` |
| `SEEDANCE_RESOLUTION` | 默认分辨率 | `` (自动) |
| `SEEDANCE_FPS` | 默认帧率 | `` (自动) |
| `SEEDANCE_AUDIO` | 默认是否生成音频 | `true` |
| `SEEDANCE_WATERMARK` | 默认水印 | `false` |

## 输入约定

一次 Seedance 生成至少要有：

- `prompt`: 生成提示词（必须）
- `images`: 参考图片（可选，支持多张）
- `videos`: 参考视频（可选）
- `audios`: 参考音频（可选）
- `assets`: 虚拟资产 URI（可选，如 `asset://asset-xxx`）

## 真人媒体处理

Gateway 有自己的虚拟资产系统。如果输入包含真人：

1. 先通过 `POST /apps/api/seedance/virtual-assets` 上传并注册为虚拟资产
2. 获取 `asset://asset-xxx` 格式的 URI
3. 在生成任务中通过 `--asset` 参数引用

已有的虚拟资产可以通过 `GET /apps/api/seedance/virtual-assets` 查询。

**注意**: 如果 Seedance 返回真人/人物/脸部/安全策略相关错误：
1. 不要删除人物，不要遮挡人物
2. 检查是否所有媒体都已注册为虚拟资产
3. 补齐未注册的媒体，重新提交
4. 如果仍失败，保存错误响应交给用户判断

## 音频规则

- TikTok 视频默认：可以有背景音乐，但不要人声
- 如果用户明确说"不要音乐/只要环境声"，设置 `--audio-gen false`
- `--audio <path>` 是参考音频文件；`--audio-gen <bool>` 才是是否让 Seedance 生成音频
- 不要自动加口播、人声讲解或字幕

## 任务状态流转

```
QUEUED → WAITING_REMOTE → PROCESSING → COMPLETED
                              ↓
                           FAILED
```

脚本会自动轮询直到任务完成或失败，轮询间隔 5 秒，最大等待 30 分钟。

## 输出 QA

每个输出至少检查：

- 视频文件是否存在且非空
- 时长是否符合预期
- 画面是否无字幕、无水印、无新增无关 logo
- 同一视频内产品、背景、场景是否一致

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `scripts/generate_seedance.mjs` | 单条视频生成 |
| `scripts/run_seedance_parallel.mjs` | 批量并发生成 |
