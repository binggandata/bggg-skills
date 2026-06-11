#!/usr/bin/env node
/**
 * run_seedance_parallel.mjs — 批量并发调用 Seedance 视频生成
 *
 * 用法:
 *   node run_seedance_parallel.mjs --config ./batch.json --concurrency 3
 *   node run_seedance_parallel.mjs --prompts-dir ./prompts/ --images-dir ./images/ --output-dir ./projects/seedance-outputs/ --concurrency 3
 *
 * batch.json 格式:
 *   [
 *     {"prompt": "...", "images": ["./a.jpg"], "output": "./out1.mp4", "duration": 5},
 *     {"prompt": "...", "assets": ["asset://asset-xxx"], "output": "./out2.mp4", "duration": 10}
 *   ]
 */

import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

const SCRIPT_DIR = path.dirname(new URL(import.meta.url).pathname);
const GENERATOR = path.join(SCRIPT_DIR, "generate_seedance.mjs");

const defaults = {
  concurrency: 3,
  outputDir: "./projects/seedance-outputs",
};

const args = parseArgs(process.argv.slice(2));

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exitCode = 1;
});

async function main() {
  const jobs = await resolveJobs(args);
  if (!jobs.length) {
    console.log("No jobs to run.");
    return;
  }

  const concurrency = Number(args.concurrency || defaults.concurrency);
  const skipExisting = Boolean(args["skip-existing"]);

  console.log(`Jobs: ${jobs.length}`);
  console.log(`Concurrency: ${concurrency}`);

  const queue = jobs.slice();
  const results = [];
  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, (_, i) =>
    runWorker(i + 1, queue, results, { skipExisting })
  );
  await Promise.all(workers);

  const failed = results.filter((r) => r.code !== 0);
  console.log(`\nDone: ${results.length - failed.length}/${results.length}`);
  if (failed.length) {
    for (const r of failed) console.error(`FAILED: ${r.job.output} code=${r.code}`);
    process.exitCode = 1;
  }
}

async function resolveJobs(args) {
  // 方式1: --config 指定 JSON 文件
  if (args.config) {
    const text = await fs.readFile(args.config, "utf-8");
    return JSON.parse(text);
  }

  // 方式2: --prompts-dir + --images-dir
  const promptsDir = args["prompts-dir"];
  const imagesDir = args["images-dir"];
  const outputDir = args["output-dir"] || defaults.outputDir;

  if (promptsDir) {
    const entries = await fs.readdir(promptsDir, { withFileTypes: true });
    const txtFiles = entries.filter((e) => e.isFile() && e.name.endsWith(".txt")).map((e) => e.name);
    const jobs = [];
    for (const txt of txtFiles) {
      const base = txt.replace(/\.txt$/, "");
      const promptPath = path.join(promptsDir, txt);
      const prompt = await fs.readFile(promptPath, "utf-8");
      const images = [];
      if (imagesDir) {
        const imgEntries = await fs.readdir(imagesDir, { withFileTypes: true });
        for (const ie of imgEntries) {
          if (ie.isFile() && ie.name.startsWith(base)) {
            images.push(path.join(imagesDir, ie.name));
          }
        }
      }
      jobs.push({
        prompt,
        images,
        output: path.join(outputDir, `${base}.mp4`),
        duration: Number(args.duration || 5),
        ratio: args.ratio || "9:16",
      });
    }
    return jobs;
  }

  return [];
}

async function runWorker(id, queue, results, options) {
  while (queue.length) {
    const job = queue.shift();
    const result = await runOne(id, job, options);
    results.push(result);
  }
}

async function runOne(workerId, job, { skipExisting }) {
  const output = path.resolve(job.output);
  if (skipExisting) {
    const exists = await fs.access(output).then(() => true).catch(() => false);
    if (exists) {
      console.log(`[w${workerId}] SKIP (exists): ${job.output}`);
      return { job, code: 0 };
    }
  }

  const cliArgs = [GENERATOR, "--prompt", job.prompt, "--output", output];
  if (job.model) cliArgs.push("--model", job.model);
  if (job.ratio) cliArgs.push("--ratio", job.ratio);
  if (job.duration) cliArgs.push("--duration", String(job.duration));
  if (job.resolution) cliArgs.push("--resolution", job.resolution);
  if (job.fps) cliArgs.push("--fps", job.fps);
  if (job.seed) cliArgs.push("--seed", job.seed);
  if (job.watermark) cliArgs.push("--watermark", job.watermark);
  if (job.audio !== undefined) cliArgs.push("--audio-gen", String(job.audio));
  if (job["camera-fixed"]) cliArgs.push("--camera-fixed", job["camera-fixed"]);
  if (job["last-frame"]) cliArgs.push("--last-frame", job["last-frame"]);
  for (const img of job.images || []) cliArgs.push("--image", img);
  for (const vid of job.videos || []) cliArgs.push("--video", vid);
  for (const aud of job.audios || []) cliArgs.push("--audio", aud);
  for (const asset of job.assets || []) cliArgs.push("--asset", asset);

  return new Promise((resolve) => {
    const child = spawn(process.execPath, cliArgs, {
      stdio: ["ignore", "pipe", "pipe"],
    });
    const prefix = `[w${workerId}]`;
    child.stdout.on("data", (chunk) => writePrefixed(process.stdout, prefix, chunk));
    child.stderr.on("data", (chunk) => writePrefixed(process.stderr, prefix, chunk));
    child.on("close", (code) => resolve({ job, code }));
  });
}

function writePrefixed(stream, prefix, chunk) {
  for (const line of String(chunk).split(/\r?\n/)) {
    if (line) stream.write(`${prefix} ${line}\n`);
  }
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
