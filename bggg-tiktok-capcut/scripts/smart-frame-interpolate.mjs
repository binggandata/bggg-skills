#!/usr/bin/env node

import { spawn } from "node:child_process";
import { constants as fsConstants } from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SKILL_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_TARGET_FPS = 60;

const options = parseArgs(process.argv.slice(2));

main().catch((error) => {
  console.error(error.stack ?? error.message);
  process.exitCode = 1;
});

async function main() {
  if (!options.input) throw new Error("Missing --input video path.");
  if (!options.output) throw new Error("Missing --output video path.");
  const input = path.resolve(options.input);
  const output = path.resolve(options.output);
  const media = await ffprobeVideo(input);
  if (!media.durationSec) throw new Error(`Could not read video duration: ${input}`);

  const backend = await resolveRifeBackend();
  const workDir = options.workDir
    ? path.resolve(options.workDir)
    : path.join(path.dirname(output), `.${path.basename(output, path.extname(output))}-rife-work`);
  if (!options.keepWork) await fs.rm(workDir, { recursive: true, force: true });
  await fs.mkdir(workDir, { recursive: true });

  const segments = await buildSegments(input, media, options);
  if (!segments.length) throw new Error("No interpolation segments were built.");

  const rendered = [];
  for (let index = 0; index < segments.length; index += 1) {
    const segment = segments[index];
    const segmentFile = path.join(workDir, "segments", `segment_${String(index + 1).padStart(3, "0")}.mp4`);
    if (segment.durationSec < 0.08) {
      await renderPassthroughSegment(input, segmentFile, segment, options.targetFps);
    } else {
      await renderRifeSegment(input, segmentFile, segment, options.targetFps, backend, path.join(workDir, `rife_${String(index + 1).padStart(3, "0")}`), options);
    }
    rendered.push(segmentFile);
  }

  const videoOnly = path.join(workDir, "interpolated_video.mp4");
  await concatSegments(rendered, videoOnly, options.targetFps);

  const coversWholeTimeline =
    Math.abs(segments[0].startSec) < 0.001 &&
    Math.abs(segments.at(-1).endSec - media.durationSec) < 0.05;
  if (options.keepAudio && media.hasAudio && coversWholeTimeline) {
    await muxOriginalAudio(videoOnly, input, output);
  } else if (options.keepAudio && media.hasAudio && segments.length === 1) {
    await muxTrimmedAudio(videoOnly, input, output, segments[0]);
  } else {
    await fs.mkdir(path.dirname(output), { recursive: true });
    await fs.copyFile(videoOnly, output);
  }

  const manifest = {
    created_at: new Date().toISOString(),
    input,
    output,
    backend: {
      engine: "rife-ncnn-vulkan",
      binary: backend.binary,
      model: backend.model,
      spatial_tta: options.spatialTta,
      temporal_tta: options.temporalTta,
      uhd: options.uhd
    },
    policy: {
      interpolation_backend: "local_rife_only",
      no_minterpolate_fallback: true,
      split_at_scene_cuts: options.sceneSplit,
      protect_hard_cuts: true,
      target_fps: options.targetFps
    },
    media,
    segments
  };
  await writeJson(`${output}.smart-frame-interpolate.json`, manifest);
  if (!options.keepWork) await fs.rm(workDir, { recursive: true, force: true });
  console.log(JSON.stringify({ output, manifest: `${output}.smart-frame-interpolate.json`, segments: segments.length }, null, 2));
}

async function buildSegments(input, media, opts) {
  if (opts.segmentsFile) {
    const raw = JSON.parse(await fs.readFile(path.resolve(opts.segmentsFile), "utf8"));
    const source = Array.isArray(raw) ? raw : raw.segments;
    if (!Array.isArray(source)) throw new Error("--segments must be a JSON array or an object with segments.");
    return source.map((item, index) => normalizeSegment(item.start ?? item.start_sec, item.end ?? item.end_sec, media.durationSec, item.label ?? `segment_${index + 1}`));
  }

  if (opts.startSec !== null || opts.endSec !== null) {
    return [normalizeSegment(opts.startSec ?? 0, opts.endSec ?? media.durationSec, media.durationSec, "requested_range")];
  }

  if (!opts.sceneSplit) return [normalizeSegment(0, media.durationSec, media.durationSec, "full_video")];
  const cuts = await detectSceneCuts(input, opts.sceneThreshold);
  const points = [0, ...cuts.filter((time) => time > 0.08 && time < media.durationSec - 0.08), media.durationSec];
  const segments = [];
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    if (end - start >= 0.03) segments.push(normalizeSegment(start, end, media.durationSec, index === 0 ? "scene_001" : `scene_${String(index + 1).padStart(3, "0")}`));
  }
  return segments;
}

function normalizeSegment(start, end, durationSec, label) {
  const startSec = Math.max(0, Number(start ?? 0));
  const endSec = Math.min(durationSec, Number(end ?? durationSec));
  if (!Number.isFinite(startSec) || !Number.isFinite(endSec) || endSec <= startSec) {
    throw new Error(`Invalid segment ${label}: ${start}-${end}`);
  }
  return {
    label,
    startSec: Number(startSec.toFixed(6)),
    endSec: Number(endSec.toFixed(6)),
    durationSec: Number((endSec - startSec).toFixed(6))
  };
}

async function renderRifeSegment(input, output, segment, targetFps, backend, workDir, opts) {
  const inputDir = path.join(workDir, "input_frames");
  const rifeDir = path.join(workDir, "rife_frames");
  await fs.rm(workDir, { recursive: true, force: true });
  await fs.mkdir(inputDir, { recursive: true });
  await fs.mkdir(rifeDir, { recursive: true });

  await runCommand("ffmpeg", [
    "-y",
    "-hide_banner",
    "-nostdin",
    "-i", input,
    "-ss", segment.startSec.toFixed(6),
    "-t", segment.durationSec.toFixed(6),
    "-an",
    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=rgb24",
    path.join(inputDir, "%08d.png")
  ]);

  const frameCount = (await fs.readdir(inputDir)).filter((name) => /\.png$/i.test(name)).length;
  if (frameCount < 2) {
    await renderPassthroughSegment(input, output, segment, targetFps);
    return;
  }

  const targetFrameCount = Math.max(2, Math.round(segment.durationSec * targetFps));
  const args = [
    "-i", inputDir,
    "-o", rifeDir,
    "-m", backend.model,
    "-n", String(targetFrameCount),
    "-j", opts.threadSpec,
    "-f", "%08d.png"
  ];
  if (opts.spatialTta) args.push("-x");
  if (opts.temporalTta) args.push("-z");
  if (opts.uhd) args.push("-u");
  await runCommand(backend.binary, args, { timeoutMs: opts.timeoutMs });

  await encodeFrameSequence(rifeDir, output, targetFps, segment.durationSec, "slow");
}

async function renderPassthroughSegment(input, output, segment, targetFps) {
  await fs.mkdir(path.dirname(output), { recursive: true });
  await runCommand("ffmpeg", [
    "-y",
    "-hide_banner",
    "-nostdin",
    "-i", input,
    "-ss", segment.startSec.toFixed(6),
    "-t", segment.durationSec.toFixed(6),
    "-an",
    "-vf", `fps=${targetFps},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p`,
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "17",
    "-pix_fmt", "yuv420p",
    output
  ]);
}

async function encodeFrameSequence(framesDir, output, targetFps, durationSec, preset) {
  await fs.mkdir(path.dirname(output), { recursive: true });
  await runCommand("ffmpeg", [
    "-y",
    "-hide_banner",
    "-nostdin",
    "-framerate", String(targetFps),
    "-i", path.join(framesDir, "%08d.png"),
    "-vf", `tpad=stop_mode=clone:stop_duration=0.500000,trim=duration=${durationSec.toFixed(6)},setpts=PTS-STARTPTS,format=yuv420p`,
    "-an",
    "-c:v", "libx264",
    "-preset", preset,
    "-crf", "17",
    "-pix_fmt", "yuv420p",
    output
  ]);
}

async function concatSegments(files, output, targetFps) {
  const listFile = `${output}.concat.txt`;
  await fs.writeFile(listFile, files.map((file) => `file '${file.replaceAll("'", "'\\''")}'`).join("\n") + "\n", "utf8");
  await runCommand("ffmpeg", [
    "-y",
    "-hide_banner",
    "-nostdin",
    "-f", "concat",
    "-safe", "0",
    "-i", listFile,
    "-vf", `fps=${targetFps},format=yuv420p`,
    "-an",
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "17",
    "-pix_fmt", "yuv420p",
    output
  ]);
}

async function muxOriginalAudio(videoOnly, source, output) {
  await fs.mkdir(path.dirname(output), { recursive: true });
  await runCommand("ffmpeg", [
    "-y",
    "-hide_banner",
    "-nostdin",
    "-i", videoOnly,
    "-i", source,
    "-map", "0:v:0",
    "-map", "1:a:0?",
    "-c:v", "copy",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    output
  ]);
}

async function muxTrimmedAudio(videoOnly, source, output, segment) {
  await fs.mkdir(path.dirname(output), { recursive: true });
  await runCommand("ffmpeg", [
    "-y",
    "-hide_banner",
    "-nostdin",
    "-i", videoOnly,
    "-ss", segment.startSec.toFixed(6),
    "-t", segment.durationSec.toFixed(6),
    "-i", source,
    "-map", "0:v:0",
    "-map", "1:a:0?",
    "-c:v", "copy",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    output
  ]);
}

async function detectSceneCuts(input, threshold) {
  const result = await runCommand("ffmpeg", [
    "-hide_banner",
    "-nostdin",
    "-i", input,
    "-vf", `select='gt(scene,${threshold})',showinfo`,
    "-an",
    "-f", "null",
    "-"
  ], { capture: true });
  const text = `${result.stdout}\n${result.stderr}`;
  return [...text.matchAll(/pts_time:([0-9.]+)/g)]
    .map((match) => Number(match[1]))
    .filter((time) => Number.isFinite(time));
}

async function ffprobeVideo(file) {
  const result = await runCommand("ffprobe", ["-v", "error", "-print_format", "json", "-show_streams", "-show_format", file], { capture: true });
  const json = JSON.parse(result.stdout);
  const video = json.streams?.find((stream) => stream.codec_type === "video") ?? {};
  const audio = json.streams?.find((stream) => stream.codec_type === "audio") ?? null;
  const duration = Number(video.duration ?? json.format?.duration ?? 0);
  return {
    durationSec: Number(duration.toFixed(6)),
    width: Number(video.width ?? 0),
    height: Number(video.height ?? 0),
    fps: parseFps(video.avg_frame_rate ?? video.r_frame_rate),
    hasAudio: Boolean(audio)
  };
}

function parseFps(value) {
  const [num, den] = String(value ?? "").split("/").map(Number);
  if (!num || !den) return null;
  return Number((num / den).toFixed(3));
}

async function resolveRifeBackend() {
  const candidates = [];
  if (process.env.BGGG_RIFE_NCNN) candidates.push({
    binary: path.resolve(process.env.BGGG_RIFE_NCNN),
    model: process.env.BGGG_RIFE_MODEL ? path.resolve(process.env.BGGG_RIFE_MODEL) : null
  });

  for (const root of [
    path.join(SKILL_ROOT, "tools", "rife-ncnn-vulkan-20221029-macos")
  ]) {
    candidates.push({ binary: path.join(root, "rife-ncnn-vulkan"), model: path.join(root, "rife-v4.6") });
  }

  const pathBinary = await which("rife-ncnn-vulkan");
  if (pathBinary) candidates.push({
    binary: pathBinary,
    model: process.env.BGGG_RIFE_MODEL ? path.resolve(process.env.BGGG_RIFE_MODEL) : path.join(path.dirname(pathBinary), "rife-v4.6")
  });

  for (const candidate of candidates) {
    if (!candidate.model) continue;
    if (await isExecutable(candidate.binary) && await pathExists(path.join(candidate.model, "flownet.param")) && await pathExists(path.join(candidate.model, "flownet.bin"))) {
      return candidate;
    }
  }

  throw new Error([
    "Smart frame interpolation requires local RIFE ncnn Vulkan.",
    "No minterpolate/optical-flow fallback is used because it can create liquid artifacts.",
    "Set BGGG_RIFE_NCNN and BGGG_RIFE_MODEL, or place the backend under bggg-tiktok-capcut/tools/rife-ncnn-vulkan-20221029-macos."
  ].join(" "));
}

async function which(command) {
  const result = await runCommand("which", [command], { capture: true, allowFailure: true });
  return result.status === 0 ? result.stdout.trim() : null;
}

async function isExecutable(file) {
  try {
    await fs.access(file, fsConstants.X_OK);
    return true;
  } catch {
    return false;
  }
}

async function pathExists(file) {
  return Boolean(await fs.stat(file).catch(() => null));
}

async function writeJson(file, value) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function runCommand(command, args, options = {}) {
  const { capture = false, allowFailure = false, timeoutMs = 3_600_000 } = options;
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error(`${command} timed out after ${timeoutMs}ms`));
    }, timeoutMs);
    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (status) => {
      clearTimeout(timer);
      if (status !== 0 && !allowFailure) reject(new Error(`${command} failed with exit ${status}: ${stderr || stdout}`));
      else resolve(capture || allowFailure ? { stdout, stderr, status } : { stdout: "", stderr: "", status });
    });
  });
}

function parseArgs(argv) {
  const opts = {
    input: null,
    output: null,
    targetFps: DEFAULT_TARGET_FPS,
    sceneSplit: true,
    sceneThreshold: 0.35,
    startSec: null,
    endSec: null,
    segmentsFile: null,
    keepAudio: true,
    keepWork: false,
    workDir: null,
    threadSpec: "2:3:2",
    spatialTta: true,
    temporalTta: true,
    uhd: false,
    timeoutMs: 3_600_000
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const take = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`Missing value for ${arg}`);
      return argv[index];
    };
    if (arg === "--input") opts.input = take();
    else if (arg === "--output") opts.output = take();
    else if (arg === "--target-fps") opts.targetFps = Number(take());
    else if (arg === "--scene-threshold") opts.sceneThreshold = Number(take());
    else if (arg === "--start") opts.startSec = Number(take());
    else if (arg === "--end") opts.endSec = Number(take());
    else if (arg === "--segments") opts.segmentsFile = take();
    else if (arg === "--work-dir") opts.workDir = take();
    else if (arg === "--threads") opts.threadSpec = take();
    else if (arg === "--timeout-ms") opts.timeoutMs = Number(take());
    else if (arg === "--keep-work") opts.keepWork = true;
    else if (arg === "--no-keep-audio") opts.keepAudio = false;
    else if (arg === "--no-scene-split") opts.sceneSplit = false;
    else if (arg === "--no-spatial-tta") opts.spatialTta = false;
    else if (arg === "--no-temporal-tta") opts.temporalTta = false;
    else if (arg === "--uhd") opts.uhd = true;
    else throw new Error(`Unknown option: ${arg}`);
  }
  if (!Number.isFinite(opts.targetFps) || opts.targetFps < 24 || opts.targetFps > 120) {
    throw new Error("--target-fps must be between 24 and 120.");
  }
  return opts;
}
