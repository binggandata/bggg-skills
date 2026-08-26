#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const SHEETS = [
  ["00_data_coverage.csv", "00 数据覆盖"],
  ["01_google_trends.csv", "01 Google Trends"],
  ["02_tiktok_videos.csv", "02 TikTok视频"],
  ["03_tiktok_comments.csv", "03 TikTok评论"],
  ["04_reddit_posts.csv", "04 Reddit帖子"],
  ["05_reddit_comments.csv", "05 Reddit评论"],
  ["06_sorftime_categories.csv", "06 Sorftime品类"],
  ["07_sorftime_products.csv", "07 Sorftime商品"],
  ["08_amazon_reviews.csv", "08 Amazon评论"],
  ["09_evidence_index.csv", "09 证据索引"],
];
const CSV_TO_SHEET = Object.fromEntries(SHEETS.map(([csv, sheet]) => [csv, sheet]));

function parseArgs(argv) {
  const at = argv.indexOf("--run-dir");
  if (at === -1 || !argv[at + 1]) throw new Error("Usage: build_research_workbook.mjs --run-dir <run>");
  return path.resolve(argv[at + 1]);
}

function parseCsv(text) {
  const rows = [];
  let row = [], cell = "", quoted = false;
  text = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i += 1; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n") { row.push(cell.replace(/\r$/, "")); rows.push(row); row = []; cell = ""; }
    else cell += ch;
  }
  if (cell || row.length) { row.push(cell.replace(/\r$/, "")); rows.push(row); }
  return rows.filter((r) => r.some((v) => v !== ""));
}

const numericHeaders = new Set([
  "count", "relative_search_interest", "stars", "likes_or_score", "views", "comments",
  "rank", "price", "monthly_sales_amount", "monthly_sales_volume", "star_rating",
  "review_count", "potential_index", "package_size", "weight", "fba_fee",
  "top100_monthly_sales_volume", "top100_monthly_sales_amount", "average_star_rating",
  "average_review_count", "average_price",
]);
const percentHeaders = new Set([
  "top3_product_sales_share", "top3_brand_sales_share", "top3_seller_sales_share",
  "new_product_3m_sales_share", "china_seller_share", "amazon_owned_sales_share",
]);
const dateHeaders = new Set(["date", "collected_at", "online_date"]);

function typedValue(header, value) {
  if (value === "") return null;
  if (dateHeaders.has(header)) {
    const localized = value.match(/^(\d{4})年(\d{1,2})月(\d{1,2})日$/);
    if (localized) return new Date(Date.UTC(Number(localized[1]), Number(localized[2]) - 1, Number(localized[3])));
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) return parsed;
  }
  if (percentHeaders.has(header) && /^-?[\d.]+%$/.test(value)) return Number(value.slice(0, -1)) / 100;
  if (numericHeaders.has(header) && /^-?[\d.]+$/.test(value)) return Number(value);
  return value;
}

function colName(index) {
  let n = index + 1, out = "";
  while (n) { n -= 1; out = String.fromCharCode(65 + (n % 26)) + out; n = Math.floor(n / 26); }
  return out;
}

function widthFor(header) {
  if (["text_raw", "title"].includes(header)) return 62;
  if (["url", "source_url", "main_image", "source_file"].includes(header)) return 42;
  if (["source_id", "native_id", "parent_id", "candidate_id"].includes(header)) return 28;
  if (["date", "date_raw", "collected_at", "online_date"].includes(header)) return 18;
  if (["theme", "query", "category_name", "top_category", "subcategory", "detail"].includes(header)) return 24;
  return Math.max(12, Math.min(22, header.length + 4));
}

function sheetNote(sheetIndex, data, headers, brief) {
  const market = brief.market_label_zh || brief.requested_market || "目标市场";
  const language = brief.language || "目标市场常用语言";
  const seedCount = (brief.seed_terms || []).length;
  const notes = [
    "本轮各渠道的实际样本量与对应工作表",
    `${market} ${seedCount || "多个"} 个子方向的相对搜索兴趣，共 ${data.length} 个时间点`,
    `${language} 内容趋势样本；不能单独证明目标地理市场`,
    `视频下可见评论；按父视频识别集中度，共 ${data.length} 条`,
    `Reddit 独立父帖；API 受阻时可来自已登录 old Reddit，共 ${data.length} 条`,
    `Reddit 评论；按父帖识别集中度并保留 collection_mode，共 ${data.length} 条`,
    `候选子方向的品类匹配与商业快照，共 ${data.length} 条`,
    `Top 1 商品搜索结果；语义筛选在报告中披露，共 ${data.length} 条`,
    "代表 ASIN 的书面评论；用于买后缺陷分析",
    `报告关键结论使用的 source_id、完整原文与 URL，共 ${data.length} 条`,
  ];
  if (sheetIndex === 8) {
    const asinColumn = headers.indexOf("asins");
    const asinCount = asinColumn >= 0 ? new Set(data.map((row) => String(row[asinColumn] || "")).filter(Boolean)).size : 0;
    return `${asinCount} 个代表 ASIN 的 ${data.length} 条书面评论；用于买后缺陷分析`;
  }
  return notes[sheetIndex];
}

const runDir = parseArgs(process.argv.slice(2));
const sourceDir = path.join(runDir, "work", "workbook-sources");
const outputDir = path.join(runDir, "report");
const qualityDir = path.join(runDir, "quality");
const previewDir = path.join(qualityDir, "workbook-previews");
const brief = JSON.parse(await fs.readFile(path.join(runDir, "00-research-brief", "research_brief.json"), "utf8"));
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
for (const name of await fs.readdir(previewDir)) {
  if (name.toLowerCase().endsWith(".png")) await fs.unlink(path.join(previewDir, name));
}

const workbook = Workbook.create();
const manifest = { workbook: "report/research_data.xlsx", sheets: [] };

for (let sheetIndex = 0; sheetIndex < SHEETS.length; sheetIndex += 1) {
  const [csvName, sheetName] = SHEETS[sheetIndex];
  const csvPath = path.join(sourceDir, csvName);
  const parsed = parseCsv(await fs.readFile(csvPath, "utf8"));
  if (!parsed.length) throw new Error(`Empty CSV source: ${csvPath}`);
  const headers = parsed[0];
  const data = parsed.slice(1).map((row) => headers.map((header, i) => {
    const value = row[i] ?? "";
    if (sheetIndex === 0 && header === "file") {
      return value.split(" / ").map((name) => CSV_TO_SHEET[name] || name).join(" / ");
    }
    return typedValue(header, value);
  }));
  const note = sheetNote(sheetIndex, data, headers, brief);
  const sheet = workbook.worksheets.add(sheetName);
  const lastCol = colName(headers.length - 1);
  const lastRow = 4 + data.length;

  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastCol}1`).merge();
  sheet.getRange("A1").values = [[sheetName]];
  sheet.getRange(`A2:${lastCol}2`).merge();
  sheet.getRange("A2").values = [[`${note}｜数据行：${data.length}`]];
  sheet.getRange(`A4:${lastCol}4`).values = [headers];
  if (data.length) sheet.getRange(`A5:${lastCol}${lastRow}`).values = data;

  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: "#195C43", font: { bold: true, color: "#FFFFFF", fontSize: 16 }, rowHeight: 30,
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:${lastCol}2`).format = {
    fill: "#E8F2EC", font: { color: "#4D675A", italic: true }, rowHeight: 24,
    verticalAlignment: "center",
  };
  sheet.getRange(`A4:${lastCol}4`).format = {
    fill: "#2D7A59", font: { bold: true, color: "#FFFFFF" }, rowHeight: 28,
    verticalAlignment: "center", wrapText: true,
    borders: { bottom: { style: "medium", color: "#195C43" } },
  };
  if (data.length) {
    sheet.getRange(`A5:${lastCol}${lastRow}`).format = {
      verticalAlignment: "top",
      borders: { insideHorizontal: { style: "thin", color: "#E1E9E4" } },
    };
  }

  headers.forEach((header, idx) => {
    const col = colName(idx);
    sheet.getRange(`${col}1:${col}${lastRow}`).format.columnWidth = widthFor(header);
    if (["text_raw", "title", "detail"].includes(header) && data.length) {
      sheet.getRange(`${col}5:${col}${lastRow}`).format.wrapText = true;
    }
    if (numericHeaders.has(header) && data.length) {
      sheet.getRange(`${col}5:${col}${lastRow}`).format.numberFormat = "#,##0.00";
    }
    if (["count", "relative_search_interest", "views", "comments", "rank", "review_count", "monthly_sales_volume", "top100_monthly_sales_volume"].includes(header) && data.length) {
      sheet.getRange(`${col}5:${col}${lastRow}`).format.numberFormat = "#,##0";
    }
    if (percentHeaders.has(header) && data.length) {
      sheet.getRange(`${col}5:${col}${lastRow}`).format.numberFormat = "0.00%";
    }
    if (dateHeaders.has(header) && data.length) {
      sheet.getRange(`${col}5:${col}${lastRow}`).format.numberFormat = header === "collected_at" ? "yyyy-mm-dd hh:mm" : "yyyy-mm-dd";
    }
  });

  const table = sheet.tables.add(`A4:${lastCol}${lastRow}`, true, `RadarTable${String(sheetIndex).padStart(2, "0")}`);
  table.style = "TableStyleMedium4";
  table.showFilterButton = true;
  sheet.freezePanes.freezeRows(4);
  manifest.sheets.push({ name: sheetName, source_csv: csvName, data_rows: data.length, columns: headers.length });
}

const outputPath = path.join(outputDir, "research_data.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

for (const item of manifest.sheets) {
  const sheet = workbook.worksheets.getItem(item.name);
  const preview = await workbook.render({ sheetName: item.name, range: `A1:${colName(Math.min(item.columns, 12) - 1)}${Math.min(item.data_rows + 4, 14)}`, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${item.name.replaceAll(" ", "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const scan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
manifest.formula_error_scan = scan.ndjson;
await fs.writeFile(path.join(qualityDir, "workbook_manifest.json"), JSON.stringify(manifest, null, 2));
console.log(JSON.stringify({ output: outputPath, sheets: manifest.sheets, formula_error_scan: scan.ndjson }));
