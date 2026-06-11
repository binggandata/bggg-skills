#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const CAPCUT_DRAFT_ROOT = process.env.CAPCUT_DRAFT_ROOT || path.join(os.homedir(), "Movies", "CapCut", "User Data", "Projects", "com.lveditor.draft");

const opts = parseArgs(process.argv.slice(2));

main().catch((error) => {
  console.error(error.stack ?? error.message);
  process.exitCode = 1;
});

async function main() {
  const draftDir = resolveDraftPath(opts.draft, opts.capcutDraftRoot);
  const result = await validateDraft(draftDir, opts.capcutDraftRoot);
  console.log(JSON.stringify(result, null, 2));
  if (!result.ok) process.exitCode = 1;
}

async function validateDraft(draftDir, draftRoot) {
  const issues = [];
  const draftName = path.basename(draftDir);
  const infoPath = path.join(draftDir, "draft_info.json");
  const metaPath = path.join(draftDir, "draft_meta_info.json");
  const rootMetaPath = path.join(draftRoot, "root_meta_info.json");
  const info = await readJson(infoPath, issues, "missing or invalid draft_info.json");
  const meta = await readJson(metaPath, issues, "missing or invalid draft_meta_info.json");
  const rootMeta = await readJson(rootMetaPath, issues, "missing or invalid root_meta_info.json");

  if (!info) return { ok: false, draft_name: draftName, draft_dir: draftDir, issues };

  if (info.name !== draftName) issues.push(`draft_info.name mismatch: ${info.name}`);
  if (!isValidDraftPath(info.path, draftDir)) issues.push(`draft_info.path mismatch: ${info.path}`);
  if (!info.id) issues.push("draft_info.id is empty");
  if (!Number(info.duration)) issues.push("draft_info.duration is empty");

  const videoTrack = (info.tracks ?? []).find((track) => track.type === "video");
  if (!videoTrack) issues.push("missing video track");
  if (!Array.isArray(videoTrack?.segments) || videoTrack.segments.length < 1) issues.push("missing video segments");

  const textTracks = (info.tracks ?? []).filter((track) => track.type === "text");
  const textMaterials = info.materials?.texts ?? [];
  const textSegmentCount = textTracks.reduce((sum, track) => sum + (track.segments?.length ?? 0), 0);
  if (textSegmentCount !== textMaterials.length) {
    issues.push(`text segment/material count mismatch: ${textSegmentCount}/${textMaterials.length}`);
  }

  for (const video of info.materials?.videos ?? []) {
    if (!video.path) issues.push(`video material ${video.id ?? "(no id)"} has empty path`);
    else if (!await exists(video.path)) issues.push(`video material missing file: ${video.path}`);
  }

  const timelineRoot = path.join(draftDir, "Timelines");
  const timelineProject = await readJson(path.join(timelineRoot, "project.json"), issues, "missing or invalid Timelines/project.json");
  const timelineDirs = (await fs.readdir(timelineRoot, { withFileTypes: true }).catch(() => []))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name);
  if (!timelineDirs.includes(info.id)) issues.push(`missing Timelines/<draft_info.id>: ${info.id}`);
  if (timelineDirs.some((name) => name !== info.id)) issues.push(`stale timeline dirs: ${timelineDirs.filter((name) => name !== info.id).join(", ")}`);
  if (timelineProject?.main_timeline_id !== info.id) issues.push(`project main_timeline_id mismatch: ${timelineProject?.main_timeline_id}`);
  if (timelineProject?.timelines?.[0]?.id !== info.id) issues.push(`project timeline id mismatch: ${timelineProject?.timelines?.[0]?.id}`);

  const nestedFiles = [
    path.join(timelineRoot, info.id, "draft_info.json"),
    path.join(timelineRoot, info.id, "draft_info.json.bak"),
    path.join(timelineRoot, info.id, "template.tmp"),
    path.join(timelineRoot, info.id, "template-2.tmp"),
    path.join(draftDir, "template-2.tmp"),
  ];
  for (const file of nestedFiles) {
    const json = await readJson(file, issues, `missing or invalid ${path.relative(draftDir, file)}`);
    const rel = path.relative(draftDir, file);
    if (path.basename(file) !== "template.tmp") {
      if (json?.id && json.id !== info.id) issues.push(`${rel} id mismatch: ${json.id}`);
      if (json?.name && json.name !== draftName) issues.push(`${rel} name mismatch: ${json.name}`);
    }
    if (json?.path && !isValidDraftPath(json.path, draftDir)) issues.push(`${rel} path mismatch: ${json.path}`);
  }

  if (meta) {
    if (meta.draft_name !== draftName) issues.push(`draft_meta_info.draft_name mismatch: ${meta.draft_name}`);
    if (meta.draft_fold_path !== draftDir) issues.push(`draft_meta_info.draft_fold_path mismatch: ${meta.draft_fold_path}`);
    if (!Number(meta.tm_draft_modified)) issues.push("draft_meta_info.tm_draft_modified is empty");
  }

  const rootEntry = rootMeta?.all_draft_store?.find((item) => item.draft_name === draftName || item.draft_fold_path === draftDir);
  if (!rootEntry) {
    issues.push("root_meta_info has no entry for this draft");
  } else {
    if (rootEntry.draft_fold_path !== draftDir) issues.push(`root draft_fold_path mismatch: ${rootEntry.draft_fold_path}`);
    if (rootEntry.draft_json_file !== infoPath) issues.push(`root draft_json_file mismatch: ${rootEntry.draft_json_file}`);
    if (!Number(rootEntry.tm_draft_modified)) issues.push("root tm_draft_modified is empty");
    if (rootEntry.draft_is_invisible) issues.push("root marks draft invisible");
  }

  const text = await collectTextFiles(draftDir);
  const staleMarkers = opts.staleMarker.filter((marker) => text.includes(marker));
  if (staleMarkers.length) issues.push(`stale template markers found: ${staleMarkers.join(", ")}`);

  return {
    ok: issues.length === 0,
    draft_name: draftName,
    draft_dir: draftDir,
    draft_id: info.id,
    duration_us: info.duration ?? null,
    video_materials: (info.materials?.videos ?? []).map((item) => item.path),
    issues,
  };
}

async function readJson(file, issues, issue) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    issues.push(issue);
    return null;
  }
}

async function collectTextFiles(root) {
  const chunks = [];
  async function walk(dir) {
    for (const entry of await fs.readdir(dir, { withFileTypes: true }).catch(() => [])) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) await walk(full);
      else if (entry.name === "ai_cut_manifest.json") {
        continue;
      }
      else if (/\.(json|tmp)$/.test(entry.name) || entry.name === "draft_settings") {
        chunks.push(await fs.readFile(full, "utf8").catch(() => ""));
      }
    }
  }
  await walk(root);
  return chunks.join("\n");
}

async function exists(file) {
  return Boolean(await fs.stat(file).catch(() => null));
}

function resolveDraftPath(value, draftRoot) {
  if (!value) throw new Error("--draft is required");
  if (value.includes(path.sep)) return path.resolve(value);
  return path.join(draftRoot, value);
}

function isValidDraftPath(value, draftDir) {
  return value === draftDir || /^##_draftpath_placeholder_[A-F0-9-]+_##$/i.test(String(value ?? ""));
}

function parseArgs(argv) {
  const opts = {
    draft: null,
    capcutDraftRoot: CAPCUT_DRAFT_ROOT,
    staleMarker: [],
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const take = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`Missing value for ${arg}`);
      return argv[index];
    };
    if (arg === "--draft") opts.draft = take();
    else if (arg === "--capcut-draft-root") opts.capcutDraftRoot = path.resolve(take());
    else if (arg === "--stale-marker") opts.staleMarker.push(take());
    else throw new Error(`Unknown option: ${arg}`);
  }
  return opts;
}
