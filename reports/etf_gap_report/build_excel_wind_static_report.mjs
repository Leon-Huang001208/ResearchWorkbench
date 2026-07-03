import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const ROOT = "/Users/leon/Desktop/Projects/AlphaFoundry";
const OUTPUT_DIR = path.join(ROOT, "outputs/etf_gap_report_20260702");
const DEFAULT_DATA_JSON = path.join(OUTPUT_DIR, "huaan_etf_gap_excel_wind_data.json");
const REPORT_PATH = path.join(OUTPUT_DIR, "华安基金ETF缺口_ExcelWind插件_近五年PE分位_静态报告.xlsx");
const LOG_DIR = path.join(ROOT, "logs");

const args = new Map(
  process.argv.slice(2).map((arg) => {
    const [key, ...rest] = arg.replace(/^--/, "").split("=");
    return [key, rest.join("=") || "true"];
  }),
);

const dataJsonPath = args.get("data") || DEFAULT_DATA_JSON;
const reportPath = args.get("output") || REPORT_PATH;
const runId = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "");
const logPath = path.join(LOG_DIR, `etf_gap_excel_wind_report_${runId}.log`);

async function log(message, payload = null) {
  const line = `${new Date().toISOString()} ${message}${payload ? ` ${JSON.stringify(payload)}` : ""}\n`;
  await fs.appendFile(logPath, line, "utf8");
  console.log(message);
}

function writeMatrix(sheet, startRow, startCol, rows) {
  if (!rows.length) return;
  sheet.getRangeByIndexes(startRow, startCol, rows.length, rows[0].length).values = rows;
}

function setWidths(sheet, widths) {
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width;
  });
}

function styleHeader(range, fill = "#174E63") {
  range.format = {
    fill,
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "middle",
  };
}

function styleSheet(sheet) {
  const used = sheet.getUsedRange(true);
  used.format.wrapText = true;
  used.format.verticalAlignment = "top";
  sheet.showGridLines = false;
}

function num(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function pct(value) {
  return num(value);
}

function shortText(value, max = 500) {
  const text = value == null ? "" : String(value);
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function sortCandidates(rows) {
  return [...rows].sort((a, b) => {
    const pa = a["近五年PE分位"] ?? 999;
    const pb = b["近五年PE分位"] ?? 999;
    if (pa !== pb) return pa - pb;
    return (b["现有ETF总规模(亿)"] ?? 0) - (a["现有ETF总规模(亿)"] ?? 0);
  });
}

async function buildWorkbook() {
  await fs.mkdir(LOG_DIR, { recursive: true });
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  await log("Excel Wind static report started", { dataJsonPath, reportPath });

  const data = JSON.parse(await fs.readFile(dataJsonPath, "utf8"));
  const meta = data.metadata || {};
  const candidates = sortCandidates(data.candidates || []);
  const coverage = data.coverage || [];
  const etfs = data.etfs || [];
  const peSeries = data.pe_series || {};

  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("Summary");
  const candSheet = workbook.worksheets.add("Candidates");
  const covSheet = workbook.worksheets.add("All Index Coverage");
  const rawSheet = workbook.worksheets.add("Raw ETF Data");
  const peSheet = workbook.worksheets.add("PE Weekly Raw");
  const checks = workbook.worksheets.add("Checks");
  const sources = workbook.worksheets.add("Sources");

  const peOkCount = coverage.filter((row) => row["Wind取数状态"] === "ok").length;
  const huaanCovered = coverage.filter((row) => row["华安是否覆盖"] === "是").length;
  const noHuaan = coverage.filter((row) => row["华安是否覆盖"] === "否").length;
  const sampleWarnings = coverage.filter((row) => row["近五年样本数"] < meta.min_samples).length;

  writeMatrix(summary, 0, 0, [
    ["华安基金ETF缺口报告（Excel Wind 插件取数，近五年PE分位）", "", "", ""],
    ["生成时间", meta.generated_at || "", "估值日期", meta.valuation_date || ""],
    ["近五年起点", meta.five_year_start || "", "筛选阈值", meta.threshold ?? ""],
    ["ETF数量", meta.etf_count ?? etfs.length, "跟踪指数数量", meta.index_count ?? coverage.length],
    ["候选指数数量", candidates.length, "PE可用指数数量", peOkCount],
    ["华安已覆盖指数", huaanCovered, "华安未覆盖指数", noHuaan],
    ["最小样本数", meta.min_samples ?? "", "样本不足/取数异常指数", sampleWarnings],
    ["数据链路", "本地Excel源表 + Excel Wind 插件 WSS/WSD 公式；未使用 Wind MCP。", "", ""],
    ["口径", "候选=华安未覆盖该跟踪指数，且近五年周度 PE(TTM) 分位 < 90%，并满足最小样本数。", "", ""],
  ]);
  summary.getRange("A1:D1").merge();
  summary.getRange("A1:D1").format = {
    fill: "#12343B",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    verticalAlignment: "middle",
  };
  summary.getRange("A2:D9").format.borders = { preset: "inside", style: "thin", color: "#C8D3D8" };
  summary.getRange("B2:D3").format.numberFormat = "yyyy-mm-dd";
  summary.getRange("D3:D3").format.numberFormat = "0.0%";
  summary.getRange("B4:D7").format.numberFormat = "#,##0";
  setWidths(summary, [18, 58, 18, 26]);

  const opportunityHeaders = [
    "跟踪指数代码",
    "跟踪指数名称",
    "PE(TTM)",
    "近五年PE分位",
    "近五年样本数",
    "PE样本截至日",
    "现有ETF数量",
    "现有ETF总规模(亿)",
    "竞品管理人",
    "代表ETF产品",
    "Wind取数状态",
  ];
  const opportunityRows = candidates.map((row) => [
    row["跟踪指数代码"],
    row["跟踪指数名称"],
    num(row["PE(TTM)"]),
    pct(row["近五年PE分位"]),
    row["近五年样本数"],
    row["PE样本截至日"],
    row["现有ETF数量"],
    num(row["现有ETF总规模(亿)"]),
    shortText(row["竞品管理人"], 260),
    shortText(row["代表ETF产品"], 360),
    row["Wind取数状态"],
  ]);
  writeMatrix(candSheet, 0, 0, [opportunityHeaders, ...opportunityRows]);
  styleHeader(candSheet.getRange("A1:K1"));
  candSheet.freezePanes.freezeRows(1);
  candSheet.getRange(`C2:C${Math.max(2, opportunityRows.length + 1)}`).format.numberFormat = "#,##0.0";
  candSheet.getRange(`D2:D${Math.max(2, opportunityRows.length + 1)}`).format.numberFormat = "0.0%";
  candSheet.getRange(`E2:H${Math.max(2, opportunityRows.length + 1)}`).format.numberFormat = "#,##0.0";
  setWidths(candSheet, [18, 26, 12, 14, 12, 14, 12, 16, 38, 62, 16]);

  const coverageHeaders = [
    "跟踪指数代码",
    "跟踪指数名称",
    "华安是否覆盖",
    "华安产品",
    "现有ETF数量",
    "现有ETF总规模(亿)",
    "竞品管理人",
    "代表ETF产品",
    "PE(TTM)",
    "近五年PE分位",
    "近五年样本数",
    "PE样本起始日",
    "PE样本截至日",
    "Wind取数状态",
    "候选",
  ];
  const coverageRows = coverage.map((row) => [
    row["跟踪指数代码"],
    row["跟踪指数名称"],
    row["华安是否覆盖"],
    shortText(row["华安产品"], 360),
    row["现有ETF数量"],
    num(row["现有ETF总规模(亿)"]),
    shortText(row["竞品管理人"], 360),
    shortText(row["代表ETF产品"], 500),
    num(row["PE(TTM)"]),
    pct(row["近五年PE分位"]),
    row["近五年样本数"],
    row["PE样本起始日"],
    row["PE样本截至日"],
    row["Wind取数状态"],
    row["候选"],
  ]);
  writeMatrix(covSheet, 0, 0, [coverageHeaders, ...coverageRows]);
  styleHeader(covSheet.getRange("A1:O1"));
  covSheet.freezePanes.freezeRows(1);
  covSheet.getRange(`F2:F${Math.max(2, coverageRows.length + 1)}`).format.numberFormat = "#,##0.0";
  covSheet.getRange(`I2:I${Math.max(2, coverageRows.length + 1)}`).format.numberFormat = "#,##0.0";
  covSheet.getRange(`J2:J${Math.max(2, coverageRows.length + 1)}`).format.numberFormat = "0.0%";
  setWidths(covSheet, [18, 26, 12, 46, 12, 16, 42, 64, 12, 14, 12, 14, 14, 16, 10]);

  const rawHeaders = [
    "基金代码",
    "基金名称",
    "类型",
    "规模(亿)",
    "管理人",
    "基金经理",
    "年初至今收益率(%)",
    "年初至今同类排名",
    "Wind3年评级",
    "跟踪指数代码原始值",
    "跟踪指数代码",
    "跟踪指数代码状态",
    "是否华安",
  ];
  const rawRows = etfs.map((row) => [
    row["基金代码"],
    row["基金名称"],
    row["类型"],
    num(row["规模(亿)"]),
    row["管理人"],
    row["基金经理"],
    num(row["年初至今收益率(%)"]),
    row["年初至今同类排名"],
    row["Wind3年评级"],
    row["跟踪指数代码原始值"],
    row["跟踪指数代码"],
    row["跟踪指数代码状态"],
    row["是否华安"],
  ]);
  writeMatrix(rawSheet, 0, 0, [rawHeaders, ...rawRows]);
  styleHeader(rawSheet.getRange("A1:M1"));
  rawSheet.freezePanes.freezeRows(1);
  rawSheet.getRange(`D2:D${Math.max(2, rawRows.length + 1)}`).format.numberFormat = "#,##0.0";
  rawSheet.getRange(`G2:G${Math.max(2, rawRows.length + 1)}`).format.numberFormat = "0.0";
  setWidths(rawSheet, [14, 34, 16, 12, 16, 22, 16, 16, 12, 18, 18, 18, 10]);

  const peRows = [];
  for (const [code, payload] of Object.entries(peSeries)) {
    const indexName = coverage.find((row) => row["跟踪指数代码"] === code)?.["跟踪指数名称"] || "";
    for (const point of payload.series || []) {
      peRows.push([code, indexName, point.date, num(point.pe_ttm)]);
    }
  }
  writeMatrix(peSheet, 0, 0, [["跟踪指数代码", "跟踪指数名称", "日期", "PE(TTM)"], ...peRows]);
  styleHeader(peSheet.getRange("A1:D1"));
  peSheet.freezePanes.freezeRows(1);
  peSheet.getRange(`C2:C${Math.max(2, peRows.length + 1)}`).format.numberFormat = "yyyy-mm-dd";
  peSheet.getRange(`D2:D${Math.max(2, peRows.length + 1)}`).format.numberFormat = "#,##0.0";
  setWidths(peSheet, [18, 26, 14, 12]);

  const failedWss = etfs.filter((row) => row["跟踪指数代码状态"] !== "ok").length;
  const failedPe = coverage.filter((row) => row["Wind取数状态"] !== "ok").length;
  writeMatrix(checks, 0, 0, [
    ["检查项", "结果", "说明"],
    ["是否使用 Wind MCP", meta.wind_mcp_used === false ? "OK" : "CHECK", "JSON 元数据 wind_mcp_used=false"],
    ["ETF跟踪指数WSS", failedWss === 0 ? "OK" : "CHECK", `${failedWss} 条 ETF 跟踪指数未成功返回`],
    ["指数PE WSD", failedPe === 0 ? "OK" : "CHECK", `${failedPe} 个指数 PE 序列未成功返回`],
    ["PE样本数", sampleWarnings === 0 ? "OK" : "CHECK", `${sampleWarnings} 个指数低于最小样本数 ${meta.min_samples}`],
    ["候选阈值", "OK", `近五年PE分位 < ${((meta.threshold || 0.9) * 100).toFixed(0)}%`],
  ]);
  styleHeader(checks.getRange("A1:C1"));
  setWidths(checks, [24, 12, 72]);

  writeMatrix(sources, 0, 0, [
    ["来源类型", "来源/公式", "用途", "备注"],
    ["本地Excel", meta.input_path || "", "ETF产品清单", "用户提供的公募基金概况表"],
    ["Excel Wind WSS", "'=@wss(\"ETF代码\",\"fund_trackindexcode\")", "拉取 ETF 跟踪指数代码", "由本机 Excel Wind 插件返回"],
    ["Excel Wind WSS", "'=@wss(\"指数代码\",\"sec_name\")", "拉取指数名称", "由本机 Excel Wind 插件返回"],
    ["Excel Wind WSD", "'=@wsd(\"指数代码\",\"pe_ttm\",\"起始日\",\"估值日\",\"Period=W\")", "拉取近五年周度 PE(TTM)", "由本机 Excel Wind 插件返回"],
    ["计算口径", "count(PE<=最新PE)/count(PE)", "近五年 PE 分位", "Python 对 Excel Wind 返回序列计算"],
    ["脚本环境", "/Users/leon/opt/anaconda3/bin/python + xlwings", "Excel 插件自动化", "系统 Python 没有 xlwings；本报告未使用 Wind MCP"],
  ]);
  styleHeader(sources.getRange("A1:D1"));
  setWidths(sources, [18, 60, 34, 62]);

  for (const sheet of [summary, candSheet, covSheet, rawSheet, peSheet, checks, sources]) {
    styleSheet(sheet);
  }

  const previewRanges = {
    Summary: "A1:D9",
    Candidates: "A1:K30",
    "All Index Coverage": "A1:O30",
    "Raw ETF Data": "A1:M30",
    Checks: "A1:C6",
    Sources: "A1:D7",
  };
  for (const [sheetName, range] of Object.entries(previewRanges)) {
    const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
    await fs.writeFile(
      path.join(OUTPUT_DIR, `${sheetName.replace(/\s+/g, "_")}_excel_wind_static.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 50 },
    summary: "final formula error scan",
  });
  await fs.writeFile(`${reportPath}.inspect.ndjson`, errors.ndjson, "utf8");

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(reportPath);
  await log("Excel Wind static report completed", {
    output: reportPath,
    candidates: candidates.length,
    coverage: coverage.length,
    peRows: peRows.length,
  });
  return reportPath;
}

buildWorkbook().catch(async (error) => {
  await log("Excel Wind static report failed", { message: error.message, stack: error.stack });
  process.exitCode = 1;
});
