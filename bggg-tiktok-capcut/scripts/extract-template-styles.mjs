#!/usr/bin/env node
/**
 * extract-template-styles.mjs — 从 CapCut 草稿中提取字幕/转场/特效样式配置
 *
 * 用法:
 *   node extract-template-styles.mjs --template "DE-chilebroskii-HV-001" --output ./my-styles.json
 *
 * 输出 JSON 包含:
 *   - texts: 字幕样式（字体、颜色、背景、描边等）
 *   - transitions: 转场配置
 *   - animations: 动画/特效配置
 *   - canvases: 画布配置
 */

import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const CAPCUT_DRAFT_ROOT = process.env.CAPCUT_DRAFT_ROOT ||
  path.join(os.homedir(), "Movies", "CapCut", "User Data", "Projects", "com.lveditor.draft");

const args = parseArgs(process.argv.slice(2));

if (args.help || args.h) {
  console.log(`
Usage: node extract-template-styles.mjs [options]

Options:
  --template <name>    Template draft name (required)
  --output <path>      Output JSON path (default: ./capcut-template-styles.json)
  --draft-root <dir>   CapCut draft root dir
  --help, -h           Show this help
`);
  process.exit(0);
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exitCode = 1;
});

async function main() {
  const templateName = args.template;
  const outputPath = args.output || "./capcut-template-styles.json";
  const draftRoot = args["draft-root"] ? path.resolve(args["draft-root"]) : CAPCUT_DRAFT_ROOT;

  if (!templateName) {
    console.error("Error: --template is required");
    process.exitCode = 1;
    return;
  }

  const templateDir = path.join(draftRoot, templateName);
  const draftPath = path.join(templateDir, "draft_info.json");

  console.log(`Reading template: ${draftPath}`);
  const draft = JSON.parse(await fs.readFile(draftPath, "utf-8"));

  const styles = extractStyles(draft);

  await fs.writeFile(path.resolve(outputPath), JSON.stringify(styles, null, 2));
  console.log(`Styles extracted: ${path.resolve(outputPath)}`);
  console.log(`  Texts: ${styles.texts.length}`);
  console.log(`  Transitions: ${styles.transitions.length}`);
  console.log(`  Animations: ${styles.animations.length}`);
  console.log(`  Effects: ${styles.effects.length}`);
  console.log(`  Canvases: ${styles.canvases.length}`);
  console.log(`  Text Templates: ${styles.textTemplates.length}`);
}

function extractStyles(draft) {
  const materials = draft.materials || {};

  return {
    meta: {
      draft_name: draft.name,
      draft_id: draft.id,
      duration: draft.duration,
      fps: draft.fps,
      canvas: draft.canvas_config,
      extracted_at: new Date().toISOString(),
    },
    texts: (materials.texts || []).map((t) => ({
      id: t.id,
      content: t.content,
      base_content: t.base_content,
      font_size: t.font_size,
      text_color: t.text_color,
      font_path: t.font_path,
      font_id: t.font_id,
      font_resource_id: t.font_resource_id,
      fonts: t.fonts,
      bold_width: t.bold_width,
      italic_degree: t.italic_degree,
      line_spacing: t.line_spacing,
      letter_spacing: t.letter_spacing,
      alignment: t.alignment,
      line_feed: t.line_feed,
      line_max_width: t.line_max_width,
      has_shadow: t.has_shadow,
      shadow_color: t.shadow_color,
      shadow_alpha: t.shadow_alpha,
      shadow_distance: t.shadow_distance,
      border_alpha: t.border_alpha,
      border_color: t.border_color,
      border_width: t.border_width,
      background_color: t.background_color,
      background_alpha: t.background_alpha,
      background_style: t.background_style,
      background_round_radius: t.background_round_radius,
      background_width: t.background_width,
      background_height: t.background_height,
      subtitle_keywords_config: t.subtitle_keywords_config,
    })),
    transitions: (materials.transitions || []).map((tr) => ({
      id: tr.id,
      name: tr.name,
      effect_id: tr.effect_id,
      resource_id: tr.resource_id,
      third_resource_id: tr.third_resource_id,
      source_platform: tr.source_platform,
      path: tr.path,
      duration: tr.duration,
      is_overlap: tr.is_overlap,
      platform: tr.platform,
      category_id: tr.category_id,
      category_name: tr.category_name,
    })),
    animations: (materials.material_animations || []).map((a) => ({
      id: a.id,
      type: a.type,
      animations: a.animations,
    })),
    effects: (materials.effects || []).map((e) => ({
      id: e.id,
      name: e.name,
      effect_id: e.effect_id,
      resource_id: e.resource_id,
      path: e.path,
    })),
    canvases: (materials.canvases || []).map((c) => ({
      id: c.id,
      type: c.type,
      color: c.color,
      blur: c.blur,
    })),
    textTemplates: (materials.text_templates || []).map((tt) => ({
      id: tt.id,
      version: tt.version,
      effect_id: tt.effect_id,
      resource_id: tt.resource_id,
      path: tt.path,
    })),
    trackStructure: {
      videoSegments: (draft.tracks || [])
        .filter((t) => t.type === "video")
        .flatMap((t) => t.segments || [])
        .map((s) => ({
          start: s.target_timerange?.start,
          duration: s.target_timerange?.duration,
          extra_material_refs: s.extra_material_refs,
        })),
      textSegments: (draft.tracks || [])
        .filter((t) => t.type === "text")
        .flatMap((t) => t.segments || [])
        .map((s) => ({
          start: s.target_timerange?.start,
          duration: s.target_timerange?.duration,
          material_id: s.material_id,
          extra_material_refs: s.extra_material_refs,
          clip: s.clip,
        })),
    },
  };
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
      out[key] = next;
      i++;
    }
  }
  return out;
}
