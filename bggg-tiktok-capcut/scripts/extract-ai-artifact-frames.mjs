#!/usr/bin/env node

import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const CAPCUT_DRAFT_ROOT = process.env.CAPCUT_DRAFT_ROOT || path.join(os.homedir(), "Movies", "CapCut", "User Data", "Projects", "com.lveditor.draft");

const options = parseArgs(process.argv.slice(2));

main().catch((error) => {
  console.error(error.stack ?? error.message);
  process.exitCode = 1;
});

async function main() {
  const jobs = await collectJobs(options);
  if (!jobs.length) throw new Error("No --video, --video-dir, or --draft inputs found.");
  await fs.mkdir(options.outputRoot, { recursive: true });
  const results = [];
  for (const job of jobs) {
    results.push(await extractJob(job, options));
  }
  const batch = {
    created_at: new Date().toISOString(),
    output_root: options.outputRoot,
    total: results.length,
    results,
  };
  await writeJson(path.join(options.outputRoot, "batch_manifest.json"), batch);
  console.log(JSON.stringify({ total: results.length, output_root: options.outputRoot }, null, 2));
}

async function collectJobs(opts) {
  const jobs = [];
  for (const video of opts.videos) {
    jobs.push(await videoToJob(video));
  }
  for (const draft of opts.drafts) {
    jobs.push(await draftToJob(resolveDraftPath(draft, opts.capcutDraftRoot)));
  }
  if (opts.videoDir) {
    for (const file of await listVideos(opts.videoDir)) {
      jobs.push(await videoToJob(file));
    }
  }
  return jobs.sort((a, b) => a.name.localeCompare(b.name, "en", { numeric: true }));
}

async function videoToJob(videoPath) {
  const probe = await ffprobeVideo(videoPath);
  return {
    name: path.basename(videoPath, path.extname(videoPath)),
    source_kind: "video",
    video_path: videoPath,
    duration_us: probe.durationUs,
    width: probe.width,
    height: probe.height,
    map_time: (targetSec) => targetSec,
  };
}

async function draftToJob(draftPath) {
  const draftFile = path.join(draftPath, "draft_info.json");
  const draft = JSON.parse(await fs.readFile(draftFile, "utf8"));
  const videoTrack = draft.tracks?.find((track) => track.type === "video");
  const videoMaterials = new Map((draft.materials?.videos ?? []).map((item) => [item.id, item]));
  const firstMaterial = videoMaterials.get(videoTrack?.segments?.[0]?.material_id) ?? draft.materials?.videos?.[0];
  if (!firstMaterial?.path) throw new Error(`Draft has no video material path: ${draftPath}`);
  const segments = (videoTrack?.segments ?? [])
    .map((segment) => ({
      targetStartUs: Number(segment.target_timerange?.start ?? 0),
      targetDurationUs: Number(segment.target_timerange?.duration ?? 0),
      sourceStartUs: Number(segment.source_timerange?.start ?? segment.target_timerange?.start ?? 0),
      sourceDurationUs: Number(segment.source_timerange?.duration ?? segment.target_timerange?.duration ?? 0),
    }))
    .filter((segment) => segment.targetDurationUs > 0)
    .sort((a, b) => a.targetStartUs - b.targetStartUs);
  return {
    name: path.basename(draftPath),
    source_kind: "capcut-draft",
    draft_path: draftPath,
    video_path: firstMaterial.path,
    duration_us: Number(draft.duration ?? 0),
    width: Number(firstMaterial.width ?? 0),
    height: Number(firstMaterial.height ?? 0),
    segments,
    map_time: (targetSec) => mapDraftTargetToSource(targetSec, segments),
  };
}

async function extractJob(job, opts) {
  const durationSec = Math.max(0.001, job.duration_us / 1_000_000);
  const frameCount = opts.frameCount ?? (durationSec >= 25 ? 40 : 20);
  const outDir = path.join(opts.outputRoot, sanitizeName(job.name));
  const framesDir = path.join(outDir, "frames");
  await fs.mkdir(framesDir, { recursive: true });
  const times = sampleTimes(durationSec, frameCount);
  const frames = [];
  for (let index = 0; index < times.length; index += 1) {
    const targetSec = times[index];
    const sourceSec = Math.min(Math.max(0, job.map_time(targetSec)), Math.max(0, durationSec - 0.04));
    const file = path.join(framesDir, `${String(index + 1).padStart(3, "0")}_t${formatTimestamp(targetSec)}.jpg`);
    await runCommand("ffmpeg", [
      "-y",
      "-ss", sourceSec.toFixed(3),
      "-i", job.video_path,
      "-frames:v", "1",
      "-vf", "format=yuvj420p",
      "-q:v", "2",
      file,
    ]);
    frames.push({
      index: index + 1,
      target_time_sec: Number(targetSec.toFixed(3)),
      source_time_sec: Number(sourceSec.toFixed(3)),
      file,
    });
  }
  const contactSheet = path.join(outDir, "contact_sheet.jpg");
  await createContactSheet(framesDir, contactSheet, frameCount);
  const reviewTemplate = {
    draft_name: job.name,
    video_path: job.video_path,
    duration_sec: Number(durationSec.toFixed(3)),
    frame_count: frameCount,
    contact_sheet: contactSheet,
    instructions: "Only mark obvious AI artifacts that affect publish quality. Do not mark ordinary aesthetic issues.",
    issues: [],
  };
  const { map_time, ...manifestJob } = job;
  const manifest = {
    created_at: new Date().toISOString(),
    ...manifestJob,
    frame_count: frameCount,
    output_dir: outDir,
    contact_sheet: contactSheet,
    frames,
  };
  await writeJson(path.join(outDir, "frames_manifest.json"), manifest);
  await writeJson(path.join(outDir, "ai_artifact_review.template.json"), reviewTemplate);
  return {
    name: job.name,
    output_dir: outDir,
    contact_sheet: contactSheet,
    frame_count: frameCount,
    duration_sec: Number(durationSec.toFixed(3)),
  };
}

async function createContactSheet(framesDir, outputFile, frameCount) {
  const { cols, rows } = tileLayout(frameCount);
  await runCommand("ffmpeg", [
    "-y",
    "-pattern_type", "glob",
    "-i", path.join(framesDir, "*.jpg"),
    "-vf", `scale=240:-1,tile=${cols}x${rows}:padding=8:margin=8:color=white`,
    "-frames:v", "1",
    "-q:v", "2",
    outputFile,
  ]);
}

async function listVideos(dir) {
  const out = [];
  async function walk(current) {
    for (const entry of await fs.readdir(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) await walk(full);
      else if (entry.isFile() && /\.(mp4|mov|webm|m4v)$/i.test(entry.name)) out.push(full);
    }
  }
  await walk(path.resolve(dir));
  return out;
}

function tileLayout(frameCount) {
  if (frameCount <= 20) return { cols: 5, rows: 4 };
  return { cols: 8, rows: 5 };
}

function sampleTimes(durationSec, count) {
  if (count <= 1) return [0];
  const safeEnd = Math.max(0, durationSec - 0.2);
  return Array.from({ length: count }, (_, index) => safeEnd * index / (count - 1));
}

function mapDraftTargetToSource(targetSec, segments) {
  const targetUs = targetSec * 1_000_000;
  const segment = segments.find((item) =>
    targetUs >= item.targetStartUs && targetUs <= item.targetStartUs + item.targetDurationUs
  ) ?? segments.at(-1);
  if (!segment) return targetSec;
  const offsetUs = Math.max(0, targetUs - segment.targetStartUs);
  const factor = segment.targetDurationUs > 0 ? segment.sourceDurationUs / segment.targetDurationUs : 1;
  return (segment.sourceStartUs + offsetUs * factor) / 1_000_000;
}

async function ffprobeVideo(file) {
  const result = await runCommand("ffprobe", ["-v", "error", "-print_format", "json", "-show_streams", "-show_format", file], true);
  const json = JSON.parse(result.stdout);
  const video = json.streams?.find((stream) => stream.codec_type === "video") ?? {};
  const duration = Number(video.duration ?? json.format?.duration ?? 0);
  return {
    durationUs: Math.round(duration * 1_000_000),
    width: Number(video.width ?? 0),
    height: Number(video.height ?? 0),
  };
}

function runCommand(command, args, capture = false) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("error", reject);
    child.on("close", (status) => {
      if (status !== 0) reject(new Error(`${command} failed with exit ${status}: ${stderr}`));
      else resolve(capture ? { stdout, stderr } : { stdout: "", stderr: "" });
    });
  });
}

async function writeJson(file, value) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function resolveDraftPath(value, draftRoot) {
  if (value.includes(path.sep)) return path.resolve(value);
  return path.join(draftRoot, value);
}

function sanitizeName(value) {
  return String(value).replace(/[^\w.-]+/g, "_");
}

function formatTimestamp(seconds) {
  const totalMs = Math.round(seconds * 1000);
  const mm = Math.floor(totalMs / 60000);
  const ss = Math.floor((totalMs % 60000) / 1000);
  const ms = totalMs % 1000;
  return `${String(mm).padStart(2, "0")}m${String(ss).padStart(2, "0")}s${String(ms).padStart(3, "0")}ms`;
}

function parseArgs(argv) {
  const opts = {
    outputRoot: path.resolve(`ai-artifact-frames-${new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z")}`),
    frameCount: null,
    videos: [],
    videoDir: null,
    drafts: [],
    capcutDraftRoot: CAPCUT_DRAFT_ROOT,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const take = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`Missing value for ${arg}`);
      return argv[index];
    };
    if (arg === "--video") opts.videos.push(path.resolve(take()));
    else if (arg === "--video-dir") opts.videoDir = path.resolve(take());
    else if (arg === "--draft") opts.drafts.push(take());
    else if (arg === "--frame-count") opts.frameCount = Number(take());
    else if (arg === "--output-root") opts.outputRoot = path.resolve(take());
    else if (arg === "--capcut-draft-root") opts.capcutDraftRoot = path.resolve(take());
    else throw new Error(`Unknown option: ${arg}`);
  }
  return opts;
}
