#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

const defaults = {
  exportsDir: "",
  runner: "",
  cwd: process.cwd(),
  workflow: "seedance_workflow",
  concurrency: 3
};

const args = parseArgs(process.argv.slice(2));

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});

async function main() {
  const exportsDir = args["exports-dir"] ?? defaults.exportsDir;
  const runner = args.runner ?? defaults.runner;
  const cwd = args.cwd ?? defaults.cwd;
  const workflow = args.workflow ?? defaults.workflow;
  const concurrency = Number(args.concurrency ?? defaults.concurrency);
  const force = Boolean(args.force);
  const skipExisting = Boolean(args["skip-existing"]) || !force;
  if (!exportsDir || !runner) {
    throw new Error("--exports-dir and --runner are required.");
  }
  const targets = await resolveTargets({ exportsDir, workflow, skipExisting });

  if (!targets.length) {
    console.log("No target folders to process.");
    return;
  }

  console.log(`TARGET_COUNT=${targets.length}`);
  console.log(`CONCURRENCY=${concurrency}`);

  const queue = targets.slice();
  const results = [];
  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, (_, index) =>
    runWorker(index + 1, queue, results, { runner, workflow, force, cwd })
  );
  await Promise.all(workers);

  const failed = results.filter((item) => item.code !== 0);
  console.log(`DONE=${results.length - failed.length}`);
  console.log(`FAILED=${failed.length}`);
  if (failed.length) {
    for (const item of failed) console.error(`FAILED_TARGET=${item.target} code=${item.code}`);
    process.exitCode = 1;
  }
}

async function resolveTargets({ exportsDir, workflow, skipExisting }) {
  if (args.targets) {
    return String(args.targets).split(",").map((item) => item.trim()).filter(Boolean);
  }
  const entries = await fs.readdir(exportsDir, { withFileTypes: true });
  const folders = entries.filter((item) => item.isDirectory() && !item.name.startsWith("_")).map((item) => item.name).sort();
  const out = [];
  for (const folder of folders) {
    const wf = path.join(exportsDir, folder, workflow);
    const output = path.join(wf, "07_seedance_gateway_run", "04-output.mp4");
    const wfOk = await exists(wf);
    if (!wfOk) continue;
    if (skipExisting && await exists(output)) continue;
    out.push(folder);
  }
  return out;
}

async function runWorker(workerId, queue, results, options) {
  while (queue.length) {
    const target = queue.shift();
    const result = await runOne(workerId, target, options);
    results.push(result);
  }
}

function runOne(workerId, target, { runner, workflow, force, cwd }) {
  return new Promise((resolve) => {
    const env = {
      ...process.env,
      QC_WORKFLOW_NAME: workflow,
      QC_TARGET_FOLDERS: target,
      QC_FORCE_RERUN: force ? "1" : "0"
    };
    const child = spawn(process.execPath, [runner], {
      cwd,
      env,
      stdio: ["ignore", "pipe", "pipe"]
    });
    const prefix = `[w${workerId} ${target}]`;
    child.stdout.on("data", (chunk) => writePrefixed(process.stdout, prefix, chunk));
    child.stderr.on("data", (chunk) => writePrefixed(process.stderr, prefix, chunk));
    child.on("close", (code) => resolve({ target, code }));
  });
}

function writePrefixed(stream, prefix, chunk) {
  for (const line of String(chunk).split(/\r?\n/)) {
    if (line) stream.write(`${prefix} ${line}\n`);
  }
}

async function exists(file) {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) out[key] = true;
    else {
      out[key] = next;
      i++;
    }
  }
  return out;
}
