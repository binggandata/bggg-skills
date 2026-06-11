#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";

const options = parseArgs(process.argv.slice(2));

main().catch((error) => {
  console.error(error.stack ?? error.message);
  process.exitCode = 1;
});

async function main() {
  const review = JSON.parse(await fs.readFile(options.review, "utf8"));
  const durationSec = Number(options.durationSec ?? review.duration_sec ?? 0);
  if (!Array.isArray(review.issues)) throw new Error("Review JSON must contain issues[].");
  const maxIssues = options.maxIssues ?? (durationSec >= 25 ? 3 : 2);
  const selected = review.issues
    .filter((issue) => issue.publish_blocking !== false)
    .sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
    .slice(0, maxIssues);
  const windows = mergeWindows(selected.map((issue) => ({
    start_sec: issueWindowStart(issue, durationSec),
    end_sec: issueWindowEnd(issue, durationSec),
    primary_issue: issue,
    fixes: recommendFixes(issue)
  })));

  const plan = {
    created_at: new Date().toISOString(),
    review_file: options.review,
    draft_name: review.draft_name ?? null,
    duration_sec: durationSec || null,
    selected_issue_count: selected.length,
    note: "Use the least visible fix that hides the publish-blocking AI artifact. Do not over-process ordinary aesthetic issues.",
    windows
  };
  await fs.mkdir(path.dirname(options.output), { recursive: true });
  await fs.writeFile(options.output, `${JSON.stringify(plan, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ selected_issue_count: selected.length, output: options.output }, null, 2));
}

function issueWindowStart(issue, durationSec) {
  if (issue.full_timeline === true) return 0;
  if (Number.isFinite(Number(issue.window_start_sec))) return Math.max(0, Number(issue.window_start_sec));
  const point = Number(issue.time_sec ?? issue.target_time_sec ?? 0);
  return Math.max(0, point - 3);
}

function issueWindowEnd(issue, durationSec) {
  const duration = Number(durationSec);
  if (issue.full_timeline === true && duration > 0) return duration;
  if (Number.isFinite(Number(issue.window_end_sec))) {
    const end = Number(issue.window_end_sec);
    return duration > 0 ? Math.min(duration, end) : end;
  }
  const point = Number(issue.time_sec ?? issue.target_time_sec ?? 0);
  return duration > 0 ? Math.min(duration, point + 3) : point + 3;
}

function recommendFixes(issue) {
  const categories = new Set(issue.categories ?? []);
  if (categories.has("text_logo_ui")) {
    return ["cover with B-roll/product close-up", "localized sticker/blur over text", "depth blur if background text is incidental"];
  }
  if (categories.has("hands") || categories.has("hand_product_intersection") || categories.has("physics")) {
    return ["cut to B-roll over the issue window", "motion blur during hand movement", "foreground product sticker/overlay if it hides the defect"];
  }
  if (categories.has("object_continuity") || categories.has("product_deformation")) {
    return ["insert transition at nearest semantic boundary", "cover with product B-roll", "short crop/zoom plus motion blur"];
  }
  if (categories.has("background") || categories.has("lighting_perspective") || categories.has("smooth_warp")) {
    return ["depth blur", "subtle filter", "B-roll if the artifact is central"];
  }
  return ["B-roll over issue window", "short motion blur", "sticker/overlay only if natural for the content"];
}

function mergeWindows(windows) {
  const sorted = windows.sort((a, b) => a.start_sec - b.start_sec);
  const merged = [];
  for (const window of sorted) {
    const last = merged.at(-1);
    if (last && window.start_sec <= last.end_sec) {
      last.end_sec = Math.max(last.end_sec, window.end_sec);
      last.issues.push(window.primary_issue);
      last.fixes = [...new Set([...last.fixes, ...window.fixes])];
    } else {
      merged.push({
        start_sec: Number(window.start_sec.toFixed(3)),
        end_sec: Number(window.end_sec.toFixed(3)),
        issues: [window.primary_issue],
        fixes: window.fixes
      });
    }
  }
  return merged;
}

function severityRank(value) {
  return { critical: 4, high: 3, medium: 2, low: 1 }[String(value ?? "").toLowerCase()] ?? 0;
}

function parseArgs(argv) {
  const opts = {
    review: null,
    output: null,
    durationSec: null,
    maxIssues: null
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const take = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`Missing value for ${arg}`);
      return argv[index];
    };
    if (arg === "--review") opts.review = path.resolve(take());
    else if (arg === "--output") opts.output = path.resolve(take());
    else if (arg === "--duration-sec") opts.durationSec = Number(take());
    else if (arg === "--max-issues") opts.maxIssues = Number(take());
    else throw new Error(`Unknown option: ${arg}`);
  }
  if (!opts.review) throw new Error("--review is required");
  if (!opts.output) opts.output = path.join(path.dirname(opts.review), "ai_artifact_fix_plan.json");
  return opts;
}
