# bggg-tiktok-seedance

[中文](./README.md) | English

`bggg-tiktok-seedance` is a Codex skill for generating TikTok/UGC videos through a user-provided Seedance Gateway. It supports reference images, reference videos, reference audio, virtual asset URIs, single jobs, and concurrent batch jobs.

## Install

```bash
mkdir -p ~/.codex/skills
cp -R bggg-tiktok-seedance ~/.codex/skills/
```

Configure your Gateway URL:

```bash
export SEEDANCE_GATEWAY_URL="https://your-seedance-gateway.example.com"
```

If your gateway requires authentication, use the deployment's environment variables, proxy, or local auth mechanism. Do not write tokens, cookies, or API keys into the skill files or commit them to the repository.

## Usage

Single generation:

```bash
node bggg-tiktok-seedance/scripts/generate_seedance.mjs \
  --prompt "A close-up skincare routine for a cleansing oil product" \
  --image ./refs/product.jpg \
  --output ./projects/seedance-output.mp4 \
  --duration 10 \
  --ratio 9:16
```

Concurrent batch generation:

```bash
node bggg-tiktok-seedance/scripts/run_seedance_parallel.mjs \
  --config ./batch-jobs.json \
  --concurrency 3 \
  --skip-existing
```

Example `batch-jobs.json`:

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

## Human References

If reference media contains real people, register it through the gateway's virtual asset system and pass the resulting `asset://...` URI. Do not mask, remove, or fake people to work around safety errors.

## Safety

Generated videos, metadata, reference assets, upload credentials, and task responses are runtime/private artifacts. Keep them under `projects/` or another local work directory, and do not commit them to the public repository.
