#!/usr/bin/env node
/**
 * create-capcut-draft.mjs — 基于模板草稿 + AI 视频生成 CapCut 草稿
 *
 * 用法:
 *   node create-capcut-draft.mjs \
 *     --template "DE-chilebroskii-HV-001" \
 *     --video "/path/to/ai-video.mp4" \
 *     --name "my-new-draft" \
 *     --captions "caption1\ncaption2\ncaption3"
 *
 *   node create-capcut-draft.mjs \
 *     --template "DE-chilebroskii-HV-001" \
 *     --video "/path/to/ai-video.mp4" \
 *     --name "my-new-draft" \
 *     --srt "/path/to/subtitles.srt"
 *
 * 环境变量:
 *   CAPCUT_DRAFT_ROOT  — CapCut 草稿根目录
 */

import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";

const CAPCUT_DRAFT_ROOT = process.env.CAPCUT_DRAFT_ROOT || path.join(os.homedir(), "Movies", "CapCut", "User Data", "Projects", "com.lveditor.draft");
const ONE_SECOND_US = 1_000_000;

const args = parseArgs(process.argv.slice(2));

if (args.help || args.h) {
  console.log(`
Usage: node create-capcut-draft.mjs [options]

Options:
  --template <name>      Template draft name (required)
  --video <path>         Input video path (required)
  --name <name>          New draft name (required)
  --captions <text>      Caption text, one per line (optional)
  --srt <path>           SRT subtitle file path (optional)
  --output-dir <dir>     CapCut draft root dir (default: ~/Movies/CapCut/...)
  --split-at <seconds>   Split video at this timestamp for transition
  --transition <name>    Transition name to use (default: from template)
  --no-transition        Do not add transition
  --no-captions          Do not add captions
  --force                Replace an existing draft folder with the same name
  --help, -h             Show this help

Examples:
  node create-capcut-draft.mjs --template DE-chilebroskii-HV-001 \\
    --video ~/workspace/seedance-skincare-15s.mp4 \\
    --name seedance-skincare-001 \\
    --captions "Double Cleanse Routine\nStep 1: Apply Oil\nStep 2: Emulsify\nStep 3: Rinse"
`);
  process.exit(0);
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exitCode = 1;
});

async function main() {
  const templateName = args.template;
  const videoPath = args.video ? path.resolve(args.video) : null;
  const draftName = args.name;
  const outputDir = args["output-dir"] ? path.resolve(args["output-dir"]) : CAPCUT_DRAFT_ROOT;

  if (!templateName || !videoPath || !draftName) {
    console.error("Error: --template, --video, and --name are required");
    process.exitCode = 1;
    return;
  }

  // 1. 读取模板草稿
  const templateDir = path.join(outputDir, templateName);
  const templateDraftPath = path.join(templateDir, "draft_info.json");
  const templateMetaPath = path.join(templateDir, "draft_meta_info.json");

  console.log(`Reading template: ${templateDraftPath}`);
  const templateDraft = JSON.parse(await fs.readFile(templateDraftPath, "utf-8"));
  let templateMeta = null;
  try {
    templateMeta = JSON.parse(await fs.readFile(templateMetaPath, "utf-8"));
  } catch {}

  // 2. 探测输入视频
  const videoInfo = await probeVideo(videoPath);
  console.log(`Video: ${videoInfo.width}x${videoInfo.height}, ${videoInfo.duration}s, ${videoInfo.fps}fps`);

  // 3. 提取模板样式
  const templateStyles = extractTemplateStyles(templateDraft);
  console.log(`Template styles: ${templateStyles.textCount} texts, ${templateStyles.transitionCount} transitions, ${templateStyles.animationCount} animations`);

  // 4. 生成新草稿
  const nowUs = Date.now() * 1000;
  const newDraft = buildDraft({
    templateDraft,
    templateMeta,
    templateStyles,
    videoPath,
    videoInfo,
    draftName,
    nowUs,
    captions: await resolveCaptions(args),
    splitAt: args["split-at"] ? Number(args["split-at"]) : null,
    noTransition: args["no-transition"],
    noCaptions: args["no-captions"],
  });

  // 5. 写入新草稿目录
  const newDraftDir = path.join(outputDir, draftName);
  if (args.force) {
    await fs.rm(newDraftDir, { recursive: true, force: true });
  }
  await fs.mkdir(newDraftDir, { recursive: true });

  // 复制模板中的非 JSON 文件（Resources, Timelines, 图片等）
  await copyTemplateAssets(templateDir, newDraftDir);
  const mediaSize = (await fs.stat(videoPath)).size;
  const newMeta = buildMeta(templateMeta, {
    draftName,
    draftRoot: outputDir,
    draftDir: newDraftDir,
    draft: newDraft,
    templateDir,
    templateName,
    videoPath,
    videoInfo,
    mediaSize,
    nowUs,
  });

  await writeDraftPackage({
    draftRoot: outputDir,
    draftName,
    draftDir: newDraftDir,
    draft: newDraft,
    meta: newMeta,
    templateDraft,
    templateDir,
    templateName,
    videoPath,
    mediaSize,
    nowUs,
  });

  // 写入 ai_cut_manifest.json
  const manifest = {
    created_at: new Date().toISOString(),
    template: templateName,
    source_video: videoPath,
    draft_name: draftName,
    draft_id: newDraft.id,
    video_info: videoInfo,
    captions: newDraft._captions || [],
  };
  await writeJson(path.join(newDraftDir, "ai_cut_manifest.json"), manifest);

  // 更新 CapCut 根索引
  await updateRootMetaInfo(outputDir, draftName, newDraftDir, videoInfo, {
    draft: newDraft,
    meta: newMeta,
    mediaSize,
    nowUs,
  });

  console.log(`\nDone: ${newDraftDir}`);
  console.log(`Draft name: ${draftName}`);
  console.log(`Draft id: ${newDraft.id}`);
  console.log(`Open/reopen CapCut to edit`);
}

// ==================== 模板样式提取 ====================

function extractTemplateStyles(draft) {
  const materials = draft.materials || {};
  const styles = {
    textCount: (materials.texts || []).length,
    transitionCount: (materials.transitions || []).length,
    animationCount: (materials.material_animations || []).length,
    texts: [],
    transitions: [],
    animations: [],
    effects: [],
    canvases: materials.canvases || [],
    textTemplates: materials.text_templates || [],
  };

  // 提取字幕样式（取第一个作为模板）
  for (const text of materials.texts || []) {
    styles.texts.push({
      id: text.id,
      content: text.content,
      base_content: text.base_content,
      font_size: text.font_size,
      text_color: text.text_color,
      font_path: text.font_path,
      font_id: text.font_id,
      font_resource_id: text.font_resource_id,
      bold_width: text.bold_width,
      italic_degree: text.italic_degree,
      line_spacing: text.line_spacing,
      letter_spacing: text.letter_spacing,
      alignment: text.alignment,
      line_feed: text.line_feed,
      line_max_width: text.line_max_width,
      subtitle_keywords_config: text.subtitle_keywords_config,
      fonts: text.fonts,
      has_shadow: text.has_shadow,
      shadow_color: text.shadow_color,
      shadow_alpha: text.shadow_alpha,
      shadow_distance: text.shadow_distance,
      border_alpha: text.border_alpha,
      border_color: text.border_color,
      border_width: text.border_width,
      background_color: text.background_color,
      background_alpha: text.background_alpha,
      background_style: text.background_style,
      background_round_radius: text.background_round_radius,
      background_width: text.background_width,
      background_height: text.background_height,
    });
  }

  // 提取转场
  for (const tr of materials.transitions || []) {
    styles.transitions.push({
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
    });
  }

  // 提取动画
  for (const anim of materials.material_animations || []) {
    styles.animations.push({
      id: anim.id,
      type: anim.type,
      animations: anim.animations,
    });
  }

  return styles;
}

// ==================== 草稿构建 ====================

function buildDraft(opts) {
  const { templateDraft, templateStyles, videoPath, videoInfo, draftName, nowUs, captions, splitAt, noTransition, noCaptions } = opts;

  const durationUs = Math.round(videoInfo.duration * ONE_SECOND_US);
  const splitUs = splitAt ? Math.round(splitAt * ONE_SECOND_US) : Math.round(durationUs / 2);
  const seg1Dur = splitUs;
  const seg2Dur = durationUs - splitUs;

  // 生成新的 UUID 映射
  const idMap = new Map();
  const newId = (oldId) => {
    if (!oldId) return oldId;
    if (!idMap.has(oldId)) {
      idMap.set(oldId, randomUUID().toUpperCase());
    }
    return idMap.get(oldId);
  };

  // 复制并修改 draft
  const draft = JSON.parse(JSON.stringify(templateDraft));

  // 更新基本信息
  draft.id = randomUUID().toUpperCase();
  draft.name = draftName;
  draft.path = "";
  draft.duration = durationUs;
  draft.create_time = nowUs;
  draft.update_time = nowUs;
  draft.fps = videoInfo.fps || 30;
  draft.canvas_config = {
    ratio: "original",
    width: videoInfo.width,
    height: videoInfo.height,
    background: null,
  };

  // 清理旧的字幕识别数据
  if (draft.config) {
    draft.config.subtitle_recognition_id = "";
    draft.config.subtitle_taskinfo = [];
    draft.config.lyrics_recognition_id = "";
    draft.config.lyrics_taskinfo = [];
  }

  // 构建 materials
  const materials = draft.materials || {};

  // 视频素材
  const videoMaterialId = randomUUID().toUpperCase();
  materials.videos = [{
    ...((materials.videos || [])[0] || {}),
    id: videoMaterialId,
    duration: durationUs,
    path: videoPath,
    media_path: "",
    width: videoInfo.width,
    height: videoInfo.height,
    material_name: path.basename(videoPath),
    local_material_id: randomUUID().toLowerCase(),
  }];

  // 清理不需要的素材类型
  materials.audios = [];
  materials.stickers = [];
  materials.beats = [];
  materials.audio_effects = [];
  materials.audio_fades = [];
  materials.video_effects = [];
  materials.plugin_effects = [];

  // 转场：保留模板中的转场，但更新 ID
  if (!noTransition && templateStyles.transitions.length > 0) {
    const tr = templateStyles.transitions[0];
    const newTrId = randomUUID().toUpperCase();
    materials.transitions = [{
      ...tr,
      id: newTrId,
    }];
  } else {
    materials.transitions = [];
  }

  // 字幕
  const textSegments = [];
  const textMaterials = [];
  const textAnimations = [];

  if (!noCaptions && captions.length > 0 && templateStyles.texts.length > 0) {
    const templateText = templateStyles.texts[0];
    const totalDuration = durationUs;
    const captionDuration = Math.floor(totalDuration / captions.length);

    for (let i = 0; i < captions.length; i++) {
      const text = captions[i];
      const start = i * captionDuration;
      const dur = (i === captions.length - 1) ? (totalDuration - start) : captionDuration;

      const textMaterialId = randomUUID().toUpperCase();
      const textSegId = randomUUID().toUpperCase();

      // 构建 text material
      const textMaterial = buildTextMaterial(templateText, textMaterialId, text);
      textMaterials.push(textMaterial);

      // 构建 text segment
      textSegments.push({
        id: textSegId,
        source_timerange: null,
        target_timerange: { start, duration: dur },
        render_timerange: { start: 0, duration: 0 },
        material_id: textMaterialId,
        extra_material_refs: [],
        render_index: 14000 + i,
        track_render_index: 1,
        clip: {
          scale: { x: 1, y: 1 },
          rotation: 0,
          transform: { x: 0, y: -0.56 },
          flip: { vertical: false, horizontal: false },
          alpha: 1,
        },
        uniform_scale: { on: true, value: 1 },
        visible: true,
        speed: 1,
        volume: 1,
        state: 0,
        enable_lut: false,
        enable_adjust: false,
        enable_hsl: false,
        group_id: "",
        enable_color_curves: true,
        enable_hsl_curves: true,
        track_attribute: 0,
        is_placeholder: false,
        template_id: "",
        template_scene: "default",
        common_keyframes: [],
        caption_info: null,
        responsive_layout: {
          enable: false,
          target_follow: "",
          size_layout: 0,
          horizontal_pos_layout: 0,
          vertical_pos_layout: 0,
        },
        enable_color_match_adjust: false,
        enable_color_correct_adjust: false,
        enable_adjust_mask: false,
        raw_segment_id: "",
        lyric_keyframes: null,
        enable_video_mask: true,
        digital_human_template_group_id: "",
        color_correct_alg_result: "",
        source: "segmentsourcenormal",
        enable_mask_stroke: false,
        enable_mask_shadow: false,
        enable_color_adjust_pro: false,
      });

      // 复制动画（如果有）
      if (templateStyles.animations.length > 0) {
        const anim = templateStyles.animations[0];
        const newAnimId = randomUUID().toUpperCase();
        textAnimations.push({
          ...anim,
          id: newAnimId,
        });
        // 把动画引用加到 segment 的 extra_material_refs
        const seg = textSegments[textSegments.length - 1];
        seg.extra_material_refs.push(newAnimId);
      }
    }
  }

  materials.texts = textMaterials;
  materials.material_animations = textAnimations;

  // 构建 tracks
  const videoTrack = {
    id: randomUUID().toUpperCase(),
    type: "video",
    segments: [],
    flag: 0,
    attribute: 0,
    name: "",
    is_default_name: true,
    path: videoPath,
  };

  // 视频分段
  const seg1Id = randomUUID().toUpperCase();
  const seg2Id = randomUUID().toUpperCase();

  const baseSeg = {
    source_timerange: { start: 0, duration: 0 },
    render_timerange: { start: 0, duration: 0 },
    desc: "",
    state: 0,
    speed: 1,
    is_loop: false,
    is_tone_modify: false,
    reverse: false,
    intensifies_audio: false,
    cartoon: false,
    volume: 1,
    last_nonzero_volume: 1,
    clip: {
      scale: { x: 1, y: 1 },
      rotation: 0,
      transform: { x: 0, y: 0 },
      flip: { vertical: false, horizontal: false },
      alpha: 1,
    },
    uniform_scale: { on: true, value: 1 },
    material_id: videoMaterialId,
    render_index: 0,
    keyframe_refs: [],
    enable_lut: true,
    enable_adjust: true,
    enable_hsl: false,
    visible: true,
    group_id: "",
    enable_color_curves: true,
    enable_hsl_curves: true,
    track_render_index: 0,
    hdr_settings: { mode: 1, intensity: 1, nits: 1000 },
    enable_color_wheels: true,
    track_attribute: 0,
    is_placeholder: false,
    template_id: "",
    enable_smart_color_adjust: false,
    template_scene: "default",
    common_keyframes: [],
    caption_info: null,
    responsive_layout: {
      enable: false,
      target_follow: "",
      size_layout: 0,
      horizontal_pos_layout: 0,
      vertical_pos_layout: 0,
    },
    enable_color_match_adjust: false,
    enable_color_correct_adjust: false,
    enable_adjust_mask: false,
    raw_segment_id: "",
    lyric_keyframes: null,
    enable_video_mask: true,
    digital_human_template_group_id: "",
    color_correct_alg_result: "",
    source: "segmentsourcenormal",
    enable_mask_stroke: false,
    enable_mask_shadow: false,
    enable_color_adjust_pro: false,
  };

  // 第一段
  const seg1 = {
    ...JSON.parse(JSON.stringify(baseSeg)),
    id: seg1Id,
    source_timerange: { start: 0, duration: seg1Dur },
    target_timerange: { start: 0, duration: seg1Dur },
  };

  // 第二段
  const seg2 = {
    ...JSON.parse(JSON.stringify(baseSeg)),
    id: seg2Id,
    source_timerange: { start: seg1Dur, duration: seg2Dur },
    target_timerange: { start: seg1Dur, duration: seg2Dur },
  };

  // 添加转场引用到第一段
  if (!noTransition && materials.transitions.length > 0) {
    const transitionId = materials.transitions[0].id;
    seg1.extra_material_refs = [
      ...(seg1.extra_material_refs || []),
      transitionId,
    ];
  }

  videoTrack.segments = [seg1, seg2];

  // 文本轨道
  const textTrack = {
    id: randomUUID().toUpperCase(),
    type: "text",
    segments: textSegments,
    flag: 1,
    attribute: 0,
    name: "",
    is_default_name: true,
  };

  draft.tracks = [videoTrack, textTrack];

  // 保留其他 materials 但清理引用
  materials.flowers = [];
  materials.tail_leaders = [];
  materials.images = [];
  materials.effects = [];
  materials.stickers = [];
  materials.audio_effects = [];
  materials.audio_fades = [];
  materials.beats = [];
  materials.video_effects = [];
  materials.plugin_effects = [];

  // 保存 captions 到草稿对象（用于 manifest）
  draft._captions = captions;

  return draft;
}

function buildTextMaterial(template, id, text) {
  const content = buildTextContent(template, text);
  return {
    recognize_task_id: "",
    id: id,
    name: randomUUID().toUpperCase(),
    recognize_text: text,
    recognize_model: "",
    punc_model: "",
    type: "text",
    content: content,
    base_content: "",
    words: { start_time: [], end_time: [], text: [] },
    current_words: { start_time: [], end_time: [], text: [] },
    global_alpha: 1,
    combo_info: { text_templates: [] },
    caption_template_info: {
      resource_id: "",
      third_resource_id: "",
      resource_name: "",
      category_id: "",
      category_name: "",
      effect_id: "",
      request_id: "",
      path: "",
      is_new: false,
      source_platform: 0,
    },
    layer_weight: 1,
    letter_spacing: template.letter_spacing || 0,
    text_curve: null,
    text_loop_on_path: false,
    offset_on_path: 0,
    enable_path_typesetting: false,
    text_exceeds_path_process_type: 0,
    text_typesetting_paths: null,
    text_typesetting_paths_file: "",
    text_typesetting_path_index: 0,
    line_spacing: template.line_spacing || 0.02,
    has_shadow: template.has_shadow || false,
    shadow_color: template.shadow_color || "",
    shadow_alpha: template.shadow_alpha || 0,
    shadow_smoothing: 0,
    shadow_distance: template.shadow_distance || 5,
    shadow_point: { x: 0, y: 0 },
    shadow_angle: -45,
    shadow_thickness_projection_enable: false,
    shadow_thickness_projection_angle: 0,
    shadow_thickness_projection_distance: 0,
    border_alpha: template.border_alpha || 0,
    border_color: template.border_color || "",
    border_width: template.border_width || 0,
    border_mode: 0,
    style_name: "",
    text_color: template.text_color || "#ffffffff",
    text_alpha: 1,
    font_name: "",
    font_title: "none",
    font_size: template.font_size || 12,
    font_path: template.font_path || "",
    font_id: template.font_id || "",
    font_resource_id: template.font_resource_id || "",
    initial_scale: 1,
    font_url: "",
    typesetting: 0,
    alignment: template.alignment || 1,
    line_feed: template.line_feed || 1,
    use_effect_default_color: true,
    is_rich_text: false,
    shape_clip_x: false,
    shape_clip_y: false,
    ktv_color: "",
    text_to_audio_ids: [],
    bold_width: template.bold_width || 0.008,
    italic_degree: template.italic_degree || 10,
    underline: false,
    underline_width: 0.05,
    underline_offset: 0.22,
    sub_type: 0,
    check_flag: 47,
    text_size: 30,
    font_category_name: "",
    font_source_platform: 0,
    font_third_resource_id: "",
    font_category_id: "",
    add_type: 0,
    operation_type: 0,
    recognize_type: 0,
    fonts: template.fonts || [],
    background_color: template.background_color || "",
    background_alpha: template.background_alpha || 1,
    background_style: template.background_style || 0,
    background_round_radius: template.background_round_radius || 0,
    background_width: template.background_width || 0.14,
    background_height: template.background_height || 0.14,
    background_vertical_offset: 0,
    background_horizontal_offset: 0,
    background_fill: "",
    single_char_bg_enable: false,
    single_char_bg_color: "",
    single_char_bg_alpha: 1,
    single_char_bg_round_radius: 0.3,
    single_char_bg_width: 0,
    single_char_bg_height: 0,
    single_char_bg_vertical_offset: 0,
    single_char_bg_horizontal_offset: 0,
    font_team_id: "",
    tts_auto_update: false,
    text_preset_resource_id: "",
    group_id: `Auto_${Date.now()}`,
    preset_id: "",
    preset_name: "",
    preset_category: "",
    preset_category_id: "",
    preset_index: 0,
    preset_has_set_alignment: false,
    force_apply_line_max_width: true,
    language: "en-US",
    relevance_segment: [],
    original_size: [],
    fixed_width: -1,
    fixed_height: -1,
    line_max_width: template.line_max_width || 0.72,
    oneline_cutoff: false,
    cutoff_postfix: "",
    subtitle_template_original_fontsize: 0,
    subtitle_keywords: null,
    inner_padding: -1,
    multi_language_current: "none",
    source_from: "",
    is_lyric_effect: false,
    lyric_group_id: "",
    lyrics_template: {
      resource_id: "",
      resource_name: "",
      panel: "",
      effect_id: "",
      path: "",
      category_id: "",
      category_name: "",
      request_id: "",
    },
    is_batch_replace: false,
    is_words_linear: false,
    ssml_content: "",
    subtitle_keywords_config: template.subtitle_keywords_config || null,
    sub_template_id: 1,
    translate_original_text: "",
    text: text,
  };
}

function buildTextContent(template, text) {
  // 尝试从模板的 content 中提取样式结构，替换文本
  try {
    const templateContent = JSON.parse(template.content || "{}");
    if (templateContent.styles && templateContent.styles.length > 0) {
      const newStyles = templateContent.styles.map((style) => ({
        ...style,
        range: [0, text.length],
      }));
      return JSON.stringify({
        ...templateContent,
        styles: newStyles,
        text: text,
      });
    }
  } catch {}

  // 回退：构建基本内容
  return JSON.stringify({
    styles: [{
      fill: {
        content: {
          solid: { color: [1, 1, 1] },
          render_type: "solid",
        },
      },
      range: [0, text.length],
      size: template.font_size || 12,
      bold: true,
    }],
    text: text,
  });
}

function buildMeta(templateMeta, ctx) {
  const durationUs = Math.round(ctx.videoInfo.duration * ONE_SECOND_US);
  const meta = templateMeta && typeof templateMeta === "object"
    ? JSON.parse(JSON.stringify(templateMeta))
    : {};
  const videoMaterial = ctx.draft.materials?.videos?.[0] || {};
  const nowSec = Math.floor(ctx.nowUs / ONE_SECOND_US);

  Object.assign(meta, {
    cloud_draft_cover: false,
    cloud_draft_sync: false,
    draft_cloud_last_action_download: false,
    draft_cover: "draft_cover.jpg",
    draft_fold_path: ctx.draftDir,
    draft_id: randomUUID().toUpperCase(),
    draft_is_ai_shorts: false,
    draft_is_cloud_temp_draft: false,
    draft_is_invisible: false,
    draft_is_web_article_video: false,
    draft_json_file: null,
    draft_name: ctx.draftName,
    draft_need_rename_folder: false,
    draft_new_version: meta.draft_new_version ?? "",
    draft_root_path: ctx.draftDir,
    draft_timeline_materials_size_: ctx.mediaSize,
    draft_type: meta.draft_type ?? "",
    tm_draft_create: ctx.nowUs,
    tm_draft_modified: ctx.nowUs,
    tm_draft_removed: 0,
    tm_duration: durationUs,
  });

  const materialItem = {
    ai_group_type: "",
    create_time: nowSec,
    duration: durationUs,
    enter_from: 0,
    extra_info: path.basename(ctx.videoPath),
    file_Path: ctx.videoPath,
    height: ctx.videoInfo.height,
    id: videoMaterial.id || randomUUID().toUpperCase(),
    import_time: nowSec,
    import_time_ms: ctx.nowUs,
    item_source: 1,
    md5: "",
    metetype: "video",
    roughcut_time_range: { duration: durationUs, start: 0 },
    sub_time_range: { duration: -1, start: -1 },
    type: 0,
    width: ctx.videoInfo.width,
  };
  meta.draft_materials = normalizeDraftMaterials(meta.draft_materials, materialItem);
  return replaceStringsDeep(meta, replacementsFor(ctx.templateName, ctx.templateDir, ctx.draftName, ctx.draftDir, ctx.videoPath));
}

function normalizeDraftMaterials(existing, videoItem) {
  const buckets = Array.isArray(existing)
    ? existing.filter((item) => item && typeof item === "object")
    : [];
  let videoBucket = buckets.find((item) => item.type === 0);
  if (!videoBucket) {
    videoBucket = { type: 0, value: [] };
    buckets.unshift(videoBucket);
  }
  videoBucket.value = [videoItem];
  for (const type of [1, 2, 3, 6, 7, 8]) {
    if (!buckets.some((item) => item.type === type)) buckets.push({ type, value: [] });
  }
  return buckets;
}

// ==================== CapCut 包同步 ====================

async function writeDraftPackage(ctx) {
  const replacements = replacementsFor(ctx.templateName, ctx.templateDir, ctx.draftName, ctx.draftDir, ctx.videoPath);
  const draft = replaceStringsDeep({ ...ctx.draft, path: ctx.draftDir }, replacements);
  const meta = replaceStringsDeep(ctx.meta, replacements);

  await writeJson(path.join(ctx.draftDir, "draft_info.json"), draft);
  await writeJson(path.join(ctx.draftDir, "draft_info.json.bak"), draft);
  await writeJson(path.join(ctx.draftDir, "template-2.tmp"), draft);
  await writeJson(path.join(ctx.draftDir, "draft_meta_info.json"), meta, null);
  await syncTimelinePackage({ ...ctx, draft, meta, replacements });
  await writeDraftSettings(ctx.draftDir, ctx.nowUs);
}

async function syncTimelinePackage(ctx) {
  const timelineRoot = path.join(ctx.draftDir, "Timelines");
  await fs.mkdir(timelineRoot, { recursive: true });
  const entries = await fs.readdir(timelineRoot, { withFileTypes: true }).catch(() => []);
  const timelineDirs = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
  const targetDir = path.join(timelineRoot, ctx.draft.id);

  if (!timelineDirs.includes(ctx.draft.id)) {
    const preferred = timelineDirs.find((name) => name === ctx.templateDraft.id) || timelineDirs[0];
    if (preferred) {
      await fs.rename(path.join(timelineRoot, preferred), targetDir);
    } else {
      await fs.mkdir(targetDir, { recursive: true });
    }
  }

  for (const name of await fs.readdir(timelineRoot).catch(() => [])) {
    const full = path.join(timelineRoot, name);
    const stat = await fs.stat(full).catch(() => null);
    if (stat?.isDirectory() && name !== ctx.draft.id) {
      await fs.rm(full, { recursive: true, force: true });
    }
  }

  await writeJson(path.join(targetDir, "draft_info.json"), ctx.draft);
  await writeJson(path.join(targetDir, "draft_info.json.bak"), ctx.draft);
  await writeJson(path.join(targetDir, "template-2.tmp"), ctx.draft);

  await writeJson(path.join(targetDir, "template.tmp"), ctx.draft);

  await writeTimelineProject(path.join(timelineRoot, "project.json"), ctx);
  await writeTimelineProject(path.join(timelineRoot, "project.json.bak"), ctx);
}

async function writeTimelineProject(file, ctx) {
  const existing = await readJsonIfExists(file);
  const project = existing && typeof existing === "object" ? replaceStringsDeep(existing, ctx.replacements) : {};
  project.version = project.version ?? 360000;
  project.create_time = ctx.nowUs;
  project.update_time = ctx.nowUs;
  project.main_timeline_id = ctx.draft.id;
  project.timelines = [{
    create_time: ctx.nowUs,
    id: ctx.draft.id,
    is_marked_delete: false,
    name: project.timelines?.[0]?.name || "时间线01",
    update_time: ctx.nowUs,
  }];
  if (!project.id) project.id = randomUUID().toUpperCase();
  await writeJson(file, project);
}

async function writeDraftSettings(draftDir, nowUs) {
  const nowSec = Math.floor(nowUs / ONE_SECOND_US);
  const file = path.join(draftDir, "draft_settings");
  const existing = await fs.readFile(file, "utf8").catch(() => "");
  const values = Object.fromEntries(existing
    .split(/\r?\n/)
    .filter((line) => line.includes("="))
    .map((line) => line.split("=", 2)));
  const text = [
    "[General]",
    `draft_create_time=${nowSec}`,
    `draft_last_edit_time=${nowSec}`,
    `real_edit_keys=${values.real_edit_keys ?? 1}`,
    `real_edit_seconds=${values.real_edit_seconds ?? 0}`,
    "",
  ].join("\n");
  await fs.writeFile(file, text, "utf8");
}

function replacementsFor(templateName, templateDir, draftName, draftDir, videoPath) {
  return [
    [templateDir, draftDir],
    [`${templateName}.mp4`, path.basename(videoPath)],
    [templateName, draftName],
  ];
}

function replaceStringsDeep(value, replacements) {
  if (Array.isArray(value)) return value.map((item) => replaceStringsDeep(item, replacements));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, replaceStringsDeep(item, replacements)]));
  }
  if (typeof value !== "string") return value;
  return replacements.reduce((text, [from, to]) => text.split(from).join(to), value);
}

async function readJsonIfExists(file) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return null;
  }
}

async function writeJson(file, value, indent = 2) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const space = indent === null ? undefined : indent;
  await fs.writeFile(file, `${JSON.stringify(value, null, space)}\n`, "utf8");
}

// ==================== 文件操作 ====================

async function copyTemplateAssets(templateDir, newDraftDir) {
  const entries = await fs.readdir(templateDir, { withFileTypes: true });
  for (const entry of entries) {
    const src = path.join(templateDir, entry.name);
    const dest = path.join(newDraftDir, entry.name);
    if (entry.name.endsWith(".json")) {
      // JSON 文件由主逻辑生成，跳过
      continue;
    }
    if (entry.isDirectory()) {
      await fs.mkdir(dest, { recursive: true });
      await copyDirRecursive(src, dest);
    } else {
      await fs.copyFile(src, dest);
    }
  }
}

async function copyDirRecursive(src, dest) {
  await fs.mkdir(dest, { recursive: true });
  const entries = await fs.readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      await copyDirRecursive(srcPath, destPath);
    } else {
      await fs.copyFile(srcPath, destPath);
    }
  }
}

// ==================== 视频探测 ====================

async function probeVideo(videoPath) {
  // 尝试找到 ffprobe
  const ffprobePath = await findFfprobe();
  return new Promise((resolve, reject) => {
    const child = spawn(ffprobePath, [
      "-v", "error",
      "-select_streams", "v:0",
      "-show_entries", "stream=width,height,r_frame_rate,codec_name,pix_fmt",
      "-show_entries", "format=duration,bit_rate",
      "-of", "json",
      videoPath,
    ], { stdio: ["ignore", "pipe", "pipe"] });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => (stdout += c));
    child.stderr.on("data", (c) => (stderr += c));
    child.on("close", (code) => {
      if (code !== 0) {
        return reject(new Error(`ffprobe failed: ${stderr}`));
      }
      const data = JSON.parse(stdout);
      const stream = (data.streams || [])[0] || {};
      const format = data.format || {};

      let fps = 30;
      if (stream.r_frame_rate) {
        const [num, den] = stream.r_frame_rate.split("/").map(Number);
        fps = den ? num / den : num;
      }

      resolve({
        width: stream.width || 1080,
        height: stream.height || 1920,
        fps: Math.round(fps),
        duration: parseFloat(format.duration) || 0,
        bitRate: parseInt(format.bit_rate) || 0,
        codec: stream.codec_name || "h264",
        pixFmt: stream.pix_fmt || "yuv420p",
      });
    });
  });
}

async function updateRootMetaInfo(draftRoot, draftName, draftDir, videoInfo, ctx) {
  const rootMetaPath = path.join(draftRoot, "root_meta_info.json");

  let rootMeta;
  try {
    rootMeta = JSON.parse(await fs.readFile(rootMetaPath, "utf-8"));
  } catch {
    rootMeta = { all_draft_store: [], draft_ids: 0, root_path: draftRoot };
  }

  let store = rootMeta.all_draft_store || [];
  const draftJsonFile = path.join(draftDir, "draft_info.json");
  const draftCover = path.join(draftDir, "draft_cover.jpg");

  const existing = store.find((item) => item.draft_name === draftName || item.draft_fold_path === draftDir) || {};
  store = store.filter((item) => item === existing || (item.draft_name !== draftName && item.draft_fold_path !== draftDir));

  const newEntry = {
    cloud_draft_cover: false,
    cloud_draft_sync: false,
    draft_cloud_last_action_download: false,
    draft_cloud_purchase_info: "",
    draft_cloud_template_id: "",
    draft_cloud_tutorial_info: "",
    draft_cloud_videocut_purchase_info: "",
    draft_cover: draftCover,
    draft_fold_path: draftDir,
    draft_is_ai_shorts: false,
    draft_is_cloud_temp_draft: false,
    draft_is_invisible: false,
    draft_is_web_article_video: false,
    draft_json_file: draftJsonFile,
    draft_name: draftName,
    draft_new_version: "",
    draft_root_path: draftRoot,
    draft_timeline_materials_size: ctx.mediaSize,
    draft_type: "",
    draft_web_article_video_enter_from: "",
    streaming_edit_draft_ready: true,
    tm_draft_cloud_completed: "",
    tm_draft_cloud_entry_id: -1,
    tm_draft_cloud_modified: 0,
    tm_draft_cloud_parent_entry_id: -1,
    tm_draft_cloud_space_id: -1,
    tm_draft_cloud_user_id: -1,
    tm_draft_create: ctx.nowUs,
    tm_draft_modified: ctx.nowUs,
    tm_draft_removed: 0,
    tm_duration: Math.round(videoInfo.duration * ONE_SECOND_US),
  };

  newEntry.draft_id = ctx.meta.draft_id || existing.draft_id || randomUUID().toUpperCase();

  const existingIndex = store.indexOf(existing);
  if (existingIndex >= 0) {
    store[existingIndex] = { ...existing, ...newEntry };
    console.log(`Updated existing index entry for: ${draftName}`);
  } else {
    store.push(newEntry);
    console.log(`Added new index entry for: ${draftName}`);
  }

  rootMeta.all_draft_store = store;
  rootMeta.draft_ids = store.length;
  rootMeta.root_path = draftRoot;
  await writeJson(rootMetaPath, rootMeta);
}

async function findFfprobe() {
  // 环境变量优先
  if (process.env.FFPROBE_PATH) return process.env.FFPROBE_PATH;

  // 常见路径
  const candidates = [
    "/opt/homebrew/bin/ffprobe",
    "/usr/local/bin/ffprobe",
    "/usr/bin/ffprobe",
    "/bin/ffprobe",
  ];
  for (const p of candidates) {
    try {
      await fs.access(p);
      return p;
    } catch {}
  }

  // 回退到 PATH 中的 ffprobe
  return "ffprobe";
}

// ==================== 字幕解析 ====================

async function resolveCaptions(args) {
  if (args["no-captions"]) return [];

  if (args.srt) {
    const srtText = await fs.readFile(path.resolve(args.srt), "utf-8");
    return parseSrt(srtText);
  }

  if (args.captions) {
    return String(args.captions).replaceAll("\\n", "\n").split(/\r?\n/).filter((l) => l.trim());
  }

  return [];
}

function parseSrt(srtText) {
  const lines = srtText.split(/\r?\n/);
  const captions = [];
  let buffer = [];
  for (const line of lines) {
    if (line.trim() === "" && buffer.length > 0) {
      const textLines = buffer.slice(2);
      captions.push(textLines.join(" ").trim());
      buffer = [];
    } else {
      buffer.push(line);
    }
  }
  if (buffer.length > 0) {
    const textLines = buffer.slice(2);
    captions.push(textLines.join(" ").trim());
  }
  return captions;
}

// ==================== 参数解析 ====================

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
