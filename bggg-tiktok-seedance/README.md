# bggg-tiktok-seedance

中文 | [English](./README_EN.md)

`bggg-tiktok-seedance` 是一个通过用户自有 Seedance Gateway 生成 TikTok/UGC 视频的 Codex skill，支持参考图片、参考视频、参考音频、虚拟资产 URI、单条生成和批量并发生成。

## 安装

```bash
mkdir -p ~/.codex/skills
cp -R bggg-tiktok-seedance ~/.codex/skills/
```

配置你的 Gateway 地址：

```bash
export SEEDANCE_GATEWAY_URL="https://your-seedance-gateway.example.com"
```

如果网关需要认证，请使用部署方提供的环境变量、代理或本机认证方式。不要把 token、cookie、API key 写进 skill 文件或提交到仓库。

## 使用

单条生成：

```bash
node bggg-tiktok-seedance/scripts/generate_seedance.mjs \
  --prompt "A close-up skincare routine for a cleansing oil product" \
  --image ./refs/product.jpg \
  --output ./projects/seedance-output.mp4 \
  --duration 10 \
  --ratio 9:16
```

批量并发：

```bash
node bggg-tiktok-seedance/scripts/run_seedance_parallel.mjs \
  --config ./batch-jobs.json \
  --concurrency 3 \
  --skip-existing
```

`batch-jobs.json` 示例：

```json
[
  {
    "prompt": "Morning skincare routine with foam cleanser",
    "images": ["./refs/cleanser.jpg"],
    "output": "./projects/seedance-outputs/video1.mp4",
    "duration": 10,
    "ratio": "9:16"
  }
]
```

## 真人素材

如果参考媒体包含真人，优先通过网关的虚拟资产系统注册为 `asset://...`，再在生成任务中引用。不要为了绕过安全错误而遮挡、删除或伪造人物。

## 注意

生成视频、metadata、参考素材、上传凭据和任务响应都属于运行产物或私有配置，应留在 `projects/` 或外部工作目录，不要提交到公开仓库。
