#!/usr/bin/env node
/**
 * generate_seedance.mjs — 调用兼容的 Seedance Gateway 生成视频
 *
 * 用法:
 *   node generate_seedance.mjs --prompt "prompt text" --output ./output.mp4
 *   node generate_seedance.mjs --prompt "prompt" --image ./ref1.jpg --image ./ref2.jpg --video ./ref.mp4 --output ./out.mp4
 *   node generate_seedance.mjs --prompt "prompt" --asset asset://asset-xxx --output ./out.mp4
 *   node generate_seedance.mjs --prompt-file ./prompt.txt --images-dir ./refs/ --output ./out.mp4
 *
 * 环境变量:
 *   SEEDANCE_GATEWAY_URL  — Gateway 地址，也可用 --gateway-url 传入
 *   SEEDANCE_MODEL        — 模型，默认 seedance-fast (ep-20260528140853-22nkm)
 *   SEEDANCE_RATIO        — 比例，默认 9:16
 *   SEEDANCE_DURATION     — 时长(秒)，默认 5
 *   SEEDANCE_RESOLUTION   — 分辨率，默认空(自动)
 *   SEEDANCE_FPS          — 帧率，默认空(自动)
 *   SEEDANCE_AUDIO        — 生成音频，默认 true
 *   SEEDANCE_WATERMARK    — 水印，默认 false
 */

import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

const POLL_INTERVAL_MS = 5000;
const MAX_POLL_MINUTES = 30;

const args = parseArgs(process.argv.slice(2));
const GATEWAY_URL = args.help || args.h ? "" : resolveGatewayUrl(args);

if (args.help || args.h) {
  console.log(`
Usage: node generate_seedance.mjs [options]

Options:
  --prompt <text>          Generation prompt (required)
  --prompt-file <path>     Read prompt from file
  --output <path>          Output video path (required)
  --gateway-url <url>      Seedance Gateway URL
  --image <path>           Reference image (repeatable)
  --video <path>           Reference video (repeatable)
  --audio <path>           Reference audio (repeatable)
  --asset <uri>            Virtual asset URI, e.g. asset://asset-xxx (repeatable)
  --model <name>           Model: seedance-fast | seedance2.0
  --ratio <ratio>          Aspect ratio: 9:16 | 16:9 | 1:1
  --duration <seconds>     Video duration in seconds
  --resolution <res>       Resolution: 480p | 720p | 1080p
  --fps <fps>              Frame rate
  --seed <seed>            Random seed
  --watermark <bool>       Add watermark: true | false
  --audio-gen <bool>       Generate audio: true | false
  --camera-fixed <bool>    Fixed camera: true | false
  --last-frame <path>      Last frame reference image
  --images-dir <path>      Directory of reference images
  --help, -h               Show this help

Environment:
  SEEDANCE_GATEWAY_URL     Gateway URL
  SEEDANCE_MODEL           Default model
  SEEDANCE_RATIO           Default ratio
  SEEDANCE_DURATION        Default duration
  SEEDANCE_RESOLUTION      Default resolution
  SEEDANCE_FPS             Default FPS
  SEEDANCE_AUDIO           Default audio generation
  SEEDANCE_WATERMARK       Default watermark
`);
  process.exit(0);
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exitCode = 1;
});

async function main() {
  const prompt = await resolvePrompt(args);
  if (!prompt) {
    console.error("Error: --prompt or --prompt-file is required");
    process.exitCode = 1;
    return;
  }

  const outputPath = args.output || args.o;
  if (!outputPath) {
    console.error("Error: --output is required");
    process.exitCode = 1;
    return;
  }

  const images = await resolveFiles(args.image || args.images || []);
  const videos = await resolveFiles(args.video || args.videos || []);
  const audios = await resolveFiles(args.audio || args.audios || []);
  const assets = resolveAssets(args.asset || args.assets || []);

  const model = process.env.SEEDANCE_MODEL || args.model || "";
  const ratio = process.env.SEEDANCE_RATIO || args.ratio || "9:16";
  const duration = Number(process.env.SEEDANCE_DURATION || args.duration || 5);
  const resolution = process.env.SEEDANCE_RESOLUTION || args.resolution || "";
  const fps = process.env.SEEDANCE_FPS || args.fps || "";
  const generateAudio = String(process.env.SEEDANCE_AUDIO || args["audio-gen"] || "true");
  const watermark = String(process.env.SEEDANCE_WATERMARK || args.watermark || "false");
  const seed = args.seed || "";
  const cameraFixed = args["camera-fixed"] || "";
  const lastFrameUrl = args["last-frame"] || "";

  console.log(`Gateway: ${GATEWAY_URL}`);
  console.log(`Prompt: ${prompt.slice(0, 100)}${prompt.length > 100 ? "..." : ""}`);
  console.log(`Model: ${model || "default"}`);
  console.log(`Ratio: ${ratio}, Duration: ${duration}s`);
  console.log(`Images: ${images.length}, Videos: ${videos.length}, Audios: ${audios.length}`);
  console.log(`Assets: ${assets.length ? assets.join(", ") : "none"}`);

  // 1. 创建任务
  const task = await createTask({
    prompt,
    model,
    ratio,
    duration,
    resolution,
    fps,
    generateAudio,
    watermark,
    seed,
    cameraFixed,
    lastFrameUrl,
    images,
    videos,
    audios,
    assets,
  });

  console.log(`Task created: ${task.id}`);
  console.log(`Status: ${task.status}`);
  console.log(`Poll URL: ${task.poll_url || task.links?.self}`);

  // 2. 轮询直到完成
  const result = await pollTask(task.id);

  if (result.status === "FAILED" || result.error) {
    console.error(`Task failed: ${result.error || result.status}`);
    process.exitCode = 1;
    return;
  }

  if (!result.output_url) {
    console.error("Task completed but no output URL found");
    console.log(JSON.stringify(result, null, 2));
    process.exitCode = 1;
    return;
  }

  // 3. 下载视频
  console.log(`Downloading: ${result.output_url}`);
  await downloadFile(result.output_url, outputPath);

  // 4. 写元数据
  const metaPath = outputPath.replace(/\.mp4$/, "").replace(/\.$/, "") + ".seedance.json";
  await fs.writeFile(metaPath, JSON.stringify({
    task_id: task.id,
    gateway: GATEWAY_URL,
    prompt,
    model,
    ratio,
    duration,
    resolution,
    status: result.status,
    output_url: result.output_url,
    created_at: task.created_at,
    completed_at: result.completed_at,
    images: images.map((i) => path.basename(i)),
    videos: videos.map((v) => path.basename(v)),
    assets,
  }, null, 2));

  console.log(`Done: ${outputPath}`);
  console.log(`Meta: ${metaPath}`);
}

async function createTask(params) {
  const form = new FormData();
  form.append("prompt", params.prompt);
  if (params.model) form.append("model", params.model);
  form.append("ratio", params.ratio);
  form.append("duration", String(params.duration));
  if (params.resolution) form.append("resolution", params.resolution);
  if (params.fps) form.append("fps", params.fps);
  if (params.seed) form.append("seed", params.seed);
  if (params.cameraFixed) form.append("camera_fixed", params.cameraFixed);
  form.append("watermark", params.watermark);
  form.append("generate_audio", params.generateAudio);
  if (params.lastFrameUrl) form.append("last_frame_url", params.lastFrameUrl);

  // 上传文件
  for (const imgPath of params.images) {
    const blob = await fileToBlob(imgPath);
    form.append("images", blob, path.basename(imgPath));
  }
  for (const vidPath of params.videos) {
    const blob = await fileToBlob(vidPath);
    form.append("videos", blob, path.basename(vidPath));
  }
  for (const audPath of params.audios) {
    const blob = await fileToBlob(audPath);
    form.append("audios", blob, path.basename(audPath));
  }

  // 资产引用通过 extra_json 传递
  if (params.assets.length) {
    const extra = {
      assets: params.assets.map((uri) => ({ type: "asset", uri })),
    };
    form.append("extra_json", JSON.stringify(extra));
  }

  const res = await fetch(`${GATEWAY_URL}/apps/api/seedance/tasks`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Create task failed: ${res.status} ${text}`);
  }

  return await res.json();
}

async function pollTask(taskId) {
  const deadline = Date.now() + MAX_POLL_MINUTES * 60 * 1000;
  const url = `${GATEWAY_URL}/apps/api/tasks/${taskId}`;
  let consecutiveErrors = 0;

  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      consecutiveErrors = 0;
      if (!res.ok) {
        console.error(`Poll error: ${res.status}`);
        await sleep(POLL_INTERVAL_MS);
        continue;
      }

      const data = await res.json();
      const status = data.status;
      console.log(`[${new Date().toISOString()}] status=${status}`);

      if (status === "COMPLETED" || status === "DONE" || status === "SUCCEEDED") {
        const outputUrl = extractOutputUrl(data);
        return { status, output_url: outputUrl, completed_at: data.completed_at, ...data };
      }

      if (status === "FAILED" || status === "ERROR" || data.error) {
        return { status: "FAILED", error: data.error || status, ...data };
      }

      await sleep(POLL_INTERVAL_MS);
    } catch (err) {
      consecutiveErrors++;
      console.error(`Poll fetch error (${consecutiveErrors}): ${err.message}`);
      if (consecutiveErrors >= 5) {
        throw new Error(`Too many consecutive poll errors: ${err.message}`);
      }
      await sleep(POLL_INTERVAL_MS);
    }
  }

  throw new Error(`Polling timeout after ${MAX_POLL_MINUTES} minutes`);
}

function extractOutputUrl(data) {
  // 尝试多种可能的路径
  const r = data.result;
  if (!r) return null;
  if (r.urls && r.urls.length) return r.urls[0];
  if (r.output_files && r.output_files.length) return r.output_files[0].url;
  if (r.output?.video_url) return r.output.video_url;
  if (r.output?.url) return r.output.url;
  if (r.video_url) return r.video_url;
  if (r.url) return r.url;
  if (r.preview?.video_url) return r.preview.video_url;
  if (r.preview?.output?.video_url) return r.preview.output.video_url;
  if (data.output_dir) return `${GATEWAY_URL}/storage/${data.output_dir}`;
  return null;
}

async function downloadFile(url, dest) {
  // 先用 Node.js http 模块尝试，失败后用 curl fallback
  const nodeFs = await import("node:fs");
  await fs.mkdir(path.dirname(dest), { recursive: true });

  // 尝试 1: Node.js http/https
  try {
    const httpMod = url.startsWith("https:") ? await import("node:https") : await import("node:http");
    await new Promise((resolve, reject) => {
      const fileStream = nodeFs.createWriteStream(dest);
      const req = httpMod.get(url, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          return downloadFile(res.headers.location, dest).then(resolve).catch(reject);
        }
        if (res.statusCode !== 200) {
          return reject(new Error(`Download failed: ${res.statusCode} ${url}`));
        }
        res.pipe(fileStream);
        fileStream.on("finish", () => {
          fileStream.close();
          resolve();
        });
      });
      req.on("error", reject);
      fileStream.on("error", reject);
    });
    return;
  } catch (err) {
    console.warn(`Node.js download failed (${err.message}), trying curl...`);
  }

  // 尝试 2: curl fallback
  await new Promise((resolve, reject) => {
    const child = spawn("curl", ["-sSL", "-o", dest, "--max-time", "120", url], {
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stderr = "";
    child.stderr.on("data", (c) => (stderr += c));
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`curl download failed: ${code} ${stderr}`));
    });
  });
}

async function fileToBlob(filePath) {
  const buffer = await fs.readFile(filePath);
  const ext = path.extname(filePath).toLowerCase();
  const mime = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
  }[ext] || "application/octet-stream";
  return new Blob([buffer], { type: mime });
}

async function resolvePrompt(args) {
  if (args.prompt) return String(args.prompt);
  if (args["prompt-file"]) {
    return await fs.readFile(args["prompt-file"], "utf-8");
  }
  return null;
}

async function resolveFiles(input) {
  const list = Array.isArray(input) ? input : input ? [input] : [];
  const out = [];
  for (const item of list) {
    const stat = await fs.stat(item).catch(() => null);
    if (stat?.isFile()) {
      out.push(path.resolve(item));
    } else if (stat?.isDirectory()) {
      const entries = await fs.readdir(item);
      for (const e of entries) {
        const fp = path.join(item, e);
        const s = await fs.stat(fp).catch(() => null);
        if (s?.isFile()) out.push(path.resolve(fp));
      }
    }
  }
  return out;
}

function resolveAssets(input) {
  const list = Array.isArray(input) ? input : input ? [input] : [];
  return list.map((a) => (a.startsWith("asset://") ? a : `asset://${a}`));
}

function resolveGatewayUrl(args) {
  const raw = args["gateway-url"] || process.env.SEEDANCE_GATEWAY_URL || "";
  if (!raw) {
    console.error("Error: set SEEDANCE_GATEWAY_URL or pass --gateway-url.");
    process.exit(1);
  }
  return String(raw).replace(/\/$/, "");
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      out[key] = true;
    } else {
      if (out[key] === undefined) out[key] = next;
      else if (Array.isArray(out[key])) out[key].push(next);
      else out[key] = [out[key], next];
      i++;
    }
  }
  return out;
}
