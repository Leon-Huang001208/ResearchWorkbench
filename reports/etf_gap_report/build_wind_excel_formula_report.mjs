import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const ROOT = "/Users/leon/Desktop/Projects/AlphaFoundry";
const DEFAULT_INPUT = "/Users/leon/Desktop/公募基金_概况.xlsx";
const NODE_MODULES = "/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const OUTPUT_DIR = path.join(ROOT, "outputs/etf_gap_report_20260702");
const LOG_DIR = path.join(ROOT, "logs");
const REPORT_PATH = path.join(OUTPUT_DIR, "华安基金ETF缺口_Wind插件公式版_近五年PE分位.xlsx");

const MAX_INDEX_ROWS = 650;
const WEEKLY_POINTS = 262;

const args = new Map(
  process.argv.slice(2).map((arg) => {
    const [key, ...rest] = arg.replace(/^--/, "").split("=");
    return [key, rest.join("=") || "true"];
  }),
);

const inputPath = args.get("input") || DEFAULT_INPUT;
const runId = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "");
const logPath = path.join(LOG_DIR, `etf_gap_wind_excel_formula_${runId}.log`);

async function log(message, payload = null) {
  const line = `${new Date().toISOString()} ${message}${payload ? ` ${JSON.stringify(payload)}` : ""}\n`;
  await fs.appendFile(logPath, line, "utf8");
  console.log(message);
}

function columnName(index) {
  let n = index + 1;
  let name = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    name = String.fromCharCode(65 + rem) + name;
    n = Math.floor((n - rem - 1) / 26);
  }
  return name;
}

function toNumber(value) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (value === null || value === undefined || value === "" || value === "--") return null;
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

async function readSourceWorkbook() {
  const input = await FileBlob.load(inputPath);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const sheet = workbook.worksheets.getItemAt(0);
  const values = sheet.getUsedRange(true).values;
  const headers = values[0];
  const rows = values
    .slice(1)
    .map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""])))
    .filter((row) => row["基金代码"] && row["基金名称"]);
  return { sheetName: sheet.name, headers, rows };
}

function writeMatrix(sheet, startRow, startCol, rows) {
  if (!rows.length) return;
  sheet.getRangeByIndexes(startRow, startCol, rows.length, rows[0].length).values = rows;
}

function writeFormulas(sheet, startRow, startCol, formulas) {
  if (!formulas.length) return;
  sheet.getRangeByIndexes(startRow, startCol, formulas.length, formulas[0].length).formulas = formulas;
}

function styleHeader(range) {
  range.format = {
    fill: "#174E63",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
  };
}

function setWidths(sheet, widths) {
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width;
  });
}

function wss(codeRef, field, options = "") {
  return options
    ? `@wss(${codeRef},"${field}",${options})`
    : `@wss(${codeRef},"${field}")`;
}

function peTtmFormula(codeRef, dateRef) {
  return `@s_val_pe_ttm(${codeRef},TEXT(${dateRef},"yyyy-mm-dd"))`;
}

async function buildWorkbook() {
  await fs.mkdir(LOG_DIR, { recursive: true });
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  await log("Wind Excel formula report started", { inputPath, nodeModules: NODE_MODULES });

  const source = await readSourceWorkbook();
  await log("Read source workbook", { sheetName: source.sheetName, rows: source.rows.length });

  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("Summary");
  const candidates = workbook.worksheets.add("Candidates");
  const coverage = workbook.worksheets.add("Index Coverage");
  const raw = workbook.worksheets.add("Raw ETF + Wind");
  const universe = workbook.worksheets.add("Index Universe");
  const peWeekly = workbook.worksheets.add("PE Weekly");
  const config = workbook.worksheets.add("Config");
  const sources = workbook.worksheets.add("Sources");

  const rawHeaders = [
    ...source.headers,
    "跟踪指数代码(Wind)",
    "跟踪指数名称(Wind)",
    "是否华安",
    "公式状态",
  ];
  const rawValues = [
    rawHeaders,
    ...source.rows.map((row) => [
      row["基金代码"],
      row["基金名称"],
      row["类型"],
      toNumber(row["年初至今收益率(%)"]),
      row["年初至今同类排名"],
      toNumber(row["年初至今年化收益率(%)"]),
      toNumber(row["年初至今最大回撤(%)"]),
      toNumber(row["规模(亿)"]),
      toNumber(row["成立年限"]),
      row["基金经理"],
      row["管理人"],
      row["Wind3年评级"],
      "",
      "",
      "",
      "",
    ]),
  ];
  writeMatrix(raw, 0, 0, rawValues);
  const rawEndRow = source.rows.length + 1;
  styleHeader(raw.getRange("A1:P1"));

  const rawFormulaRows = [];
  for (let row = 2; row <= rawEndRow; row += 1) {
    rawFormulaRows.push([
      `=IFERROR(${wss(`A${row}`, "fund_trackindexcode")},"")`,
      `=IFERROR(${wss(`M${row}`, "sec_name")},"")`,
      `=IF(OR(ISNUMBER(SEARCH("华安",K${row})),ISNUMBER(SEARCH("华安",N${row}))),"是","否")`,
      `=IF(M${row}="","等待Wind刷新","ok")`,
    ]);
  }
  writeFormulas(raw, 1, 12, rawFormulaRows);
  raw.getRange(`D2:D${rawEndRow}`).format.numberFormat = "0.0";
  raw.getRange(`F2:H${rawEndRow}`).format.numberFormat = "0.0";
  raw.getRange(`I2:I${rawEndRow}`).format.numberFormat = "0.0";
  raw.freezePanes.freezeRows(1);
  setWidths(raw, [14, 34, 16, 14, 16, 16, 16, 12, 10, 22, 16, 12, 18, 24, 10, 14]);
  raw.showGridLines = false;

  writeMatrix(config, 0, 0, [
    ["参数", "值", "说明"],
    ["估值日期", "", "默认 TODAY()；可改成指定日期"],
    ["近五年起始日", "", "由估值日期向前 60 个月"],
    ["观察频率", "周度", "PE Weekly 每周一个观测点，共 262 个点"],
    ["候选阈值", 0.9, "近五年 PE(TTM) 分位 < 90%"],
    ["ETF 跟踪指数字段", "fund_trackindexcode", "Wind Excel WSS 字段"],
    ["指数 PE 公式", "s_val_pe_ttm", "Wind Excel 插件函数"],
    ["刷新方式", "打开 Excel 并登录 Wind 后，全部刷新/重新计算", "不经过 Wind MCP"],
  ]);
  writeFormulas(config, 1, 1, [["=TODAY()"], ["=EDATE(B2,-60)"]]);
  config.getRange("B2:B3").format.numberFormat = "yyyy-mm-dd";
  config.getRange("B5:B5").format.numberFormat = "0.0%";
  styleHeader(config.getRange("A1:C1"));
  setWidths(config, [22, 28, 70]);
  config.showGridLines = false;

  writeMatrix(universe, 0, 0, [["跟踪指数代码", "跟踪指数名称"]]);
  writeFormulas(universe, 1, 0, [
    [`=SORT(UNIQUE(FILTER('Raw ETF + Wind'!M2:M${rawEndRow},'Raw ETF + Wind'!M2:M${rawEndRow}<>"")))`],
  ]);
  writeFormulas(universe, 1, 1, [
    [`=IFERROR(XLOOKUP(A2#,'Raw ETF + Wind'!M2:M${rawEndRow},'Raw ETF + Wind'!N2:N${rawEndRow},""),"")`],
  ]);
  styleHeader(universe.getRange("A1:B1"));
  setWidths(universe, [18, 28]);
  universe.showGridLines = false;

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
    "候选",
    "刷新状态",
  ];
  writeMatrix(coverage, 0, 0, [coverageHeaders]);
  const coverageFormulas = [];
  for (let row = 2; row <= MAX_INDEX_ROWS + 1; row += 1) {
    const peRow = row;
    coverageFormulas.push([
      `=IFERROR(INDEX('Index Universe'!$A$2:$A$${MAX_INDEX_ROWS + 1},ROW()-1),"")`,
      `=IF($A${row}="","",IFERROR(XLOOKUP($A${row},'Raw ETF + Wind'!$M$2:$M$${rawEndRow},'Raw ETF + Wind'!$N$2:$N$${rawEndRow},""),""))`,
      `=IF($A${row}="","",IF(COUNTIFS('Raw ETF + Wind'!$M$2:$M$${rawEndRow},$A${row},'Raw ETF + Wind'!$O$2:$O$${rawEndRow},"是")>0,"是","否"))`,
      `=IF($A${row}="","",IFERROR(TEXTJOIN("；",TRUE,FILTER('Raw ETF + Wind'!$A$2:$A$${rawEndRow}&" "&'Raw ETF + Wind'!$B$2:$B$${rawEndRow},('Raw ETF + Wind'!$M$2:$M$${rawEndRow}=$A${row})*('Raw ETF + Wind'!$O$2:$O$${rawEndRow}="是"))),""))`,
      `=IF($A${row}="","",COUNTIF('Raw ETF + Wind'!$M$2:$M$${rawEndRow},$A${row}))`,
      `=IF($A${row}="","",SUMIF('Raw ETF + Wind'!$M$2:$M$${rawEndRow},$A${row},'Raw ETF + Wind'!$H$2:$H$${rawEndRow}))`,
      `=IF($A${row}="","",IFERROR(TEXTJOIN("；",TRUE,UNIQUE(FILTER('Raw ETF + Wind'!$K$2:$K$${rawEndRow},'Raw ETF + Wind'!$M$2:$M$${rawEndRow}=$A${row}))),""))`,
      `=IF($A${row}="","",IFERROR(TEXTJOIN("；",TRUE,FILTER('Raw ETF + Wind'!$A$2:$A$${rawEndRow}&" "&'Raw ETF + Wind'!$B$2:$B$${rawEndRow},'Raw ETF + Wind'!$M$2:$M$${rawEndRow}=$A${row})),""))`,
      `=IF($A${row}="","",IFERROR(${peTtmFormula(`$A${row}`, "Config!$B$2")},""))`,
      `=IF($A${row}="","",IFERROR(PERCENTRANK.INC(FILTER('PE Weekly'!$B${peRow}:$${columnName(WEEKLY_POINTS)}${peRow},ISNUMBER('PE Weekly'!$B${peRow}:$${columnName(WEEKLY_POINTS)}${peRow})),I${row}),""))`,
      `=IF($A${row}="","",COUNT('PE Weekly'!$B${peRow}:$${columnName(WEEKLY_POINTS)}${peRow}))`,
      `=IF($A${row}="","",IF(AND(C${row}="否",ISNUMBER(J${row}),J${row}<Config!$B$5),"是","否"))`,
      `=IF($A${row}="","",IF(K${row}<30,"样本不足/等待Wind刷新","ok"))`,
    ]);
  }
  writeFormulas(coverage, 1, 0, coverageFormulas);
  styleHeader(coverage.getRange("A1:M1"));
  coverage.getRange(`F2:F${MAX_INDEX_ROWS + 1}`).format.numberFormat = "#,##0.0";
  coverage.getRange(`I2:I${MAX_INDEX_ROWS + 1}`).format.numberFormat = "#,##0.0";
  coverage.getRange(`J2:J${MAX_INDEX_ROWS + 1}`).format.numberFormat = "0.0%";
  coverage.freezePanes.freezeRows(1);
  setWidths(coverage, [18, 26, 12, 48, 12, 16, 42, 70, 12, 14, 12, 10, 18]);
  coverage.showGridLines = false;

  const peHeaders = ["跟踪指数代码"];
  for (let point = 0; point < WEEKLY_POINTS; point += 1) {
    peHeaders.push("");
  }
  writeMatrix(peWeekly, 0, 0, [peHeaders]);
  const dateHeaderFormulas = [];
  for (let point = 0; point < WEEKLY_POINTS; point += 1) {
    dateHeaderFormulas.push(`=Config!$B$3+${point * 7}`);
  }
  writeFormulas(peWeekly, 0, 1, [dateHeaderFormulas]);
  const peFormulas = [];
  for (let row = 2; row <= MAX_INDEX_ROWS + 1; row += 1) {
    const formulaRow = [`='Index Coverage'!A${row}`];
    for (let point = 0; point < WEEKLY_POINTS; point += 1) {
      const col = columnName(point + 1);
      formulaRow.push(`=IF($A${row}="","",IFERROR(${peTtmFormula(`$A${row}`, `${col}$1`)},""))`);
    }
    peFormulas.push(formulaRow);
  }
  writeFormulas(peWeekly, 1, 0, peFormulas);
  styleHeader(peWeekly.getRangeByIndexes(0, 0, 1, WEEKLY_POINTS + 1));
  peWeekly.getRangeByIndexes(0, 1, 1, WEEKLY_POINTS).format.numberFormat = "yyyy-mm-dd";
  peWeekly.getRangeByIndexes(1, 1, MAX_INDEX_ROWS, WEEKLY_POINTS).format.numberFormat = "#,##0.0";
  peWeekly.freezePanes.freezeRows(1);
  peWeekly.freezePanes.freezeColumns(1);
  peWeekly.showGridLines = false;

  writeMatrix(candidates, 0, 0, [coverageHeaders]);
  writeFormulas(candidates, 1, 0, [
    [`=FILTER('Index Coverage'!A2:M${MAX_INDEX_ROWS + 1},'Index Coverage'!L2:L${MAX_INDEX_ROWS + 1}="是","暂无候选或等待Wind刷新")`],
  ]);
  styleHeader(candidates.getRange("A1:M1"));
  setWidths(candidates, [18, 26, 12, 48, 12, 16, 42, 70, 12, 14, 12, 10, 18]);
  candidates.freezePanes.freezeRows(1);
  candidates.showGridLines = false;

  writeMatrix(summary, 0, 0, [
    ["华安基金ETF缺口 - Wind插件公式版（近五年PE分位）", "", "", ""],
    ["使用方式", "打开本工作簿 -> 登录 Wind Excel 插件 -> 全部刷新/重新计算。", "", ""],
    ["数据链路", "所有 ETF 跟踪指数、指数 PE 均由 Excel Wind 插件公式拉取；本生成脚本不调用 Wind MCP。", "", ""],
    ["筛选条件", "华安未覆盖该跟踪指数，且近五年 PE(TTM) 分位 < 90%。", "", ""],
    ["原始ETF数量", source.rows.length, "唯一指数槽位上限", MAX_INDEX_ROWS],
    ["估值日期", "", "近五年起始日", ""],
    ["候选数量", "", "PE可用指数数", ""],
    ["", "", "", ""],
    ["说明", "如 Candidates 为空，通常是 Wind 公式还没刷新；先看 Raw ETF + Wind 和 PE Weekly 的刷新状态。", "", ""],
  ]);
  writeFormulas(summary, 5, 1, [["=Config!B2"]]);
  writeFormulas(summary, 5, 3, [["=Config!B3"]]);
  writeFormulas(summary, 6, 1, [[`=COUNTIF('Index Coverage'!L2:L${MAX_INDEX_ROWS + 1},"是")`]]);
  writeFormulas(summary, 6, 3, [[`=COUNTIF('Index Coverage'!M2:M${MAX_INDEX_ROWS + 1},"ok")`]]);
  summary.getRange("A1:D1").merge();
  summary.getRange("A1:D1").format = { fill: "#12343B", font: { bold: true, color: "#FFFFFF", size: 16 } };
  summary.getRange("B6:B6").format.numberFormat = "yyyy-mm-dd";
  summary.getRange("D6:D6").format.numberFormat = "yyyy-mm-dd";
  summary.getRange("B7:B7").format.numberFormat = "#,##0";
  summary.getRange("D7:D7").format.numberFormat = "#,##0";
  summary.getRange("A2:D9").format.borders = { preset: "inside", style: "thin", color: "#C8D3D8" };
  setWidths(summary, [18, 72, 18, 28]);
  summary.showGridLines = false;

  writeMatrix(sources, 0, 0, [
    ["来源类型", "来源/公式", "用途", "备注"],
    ["本地Excel", inputPath, "ETF产品清单", "用户提供"],
    ["Wind Excel WSS", '\'=@wss("ETF代码","fund_trackindexcode")', "拉取 ETF 跟踪指数代码", "由 Excel Wind 插件刷新"],
    ["Wind Excel WSS", '\'=@wss("指数代码","sec_name")', "拉取指数名称", "由 Excel Wind 插件刷新"],
    ["Wind Excel 函数", '\'=@s_val_pe_ttm("指数代码","yyyy-mm-dd")', "拉取指数 PE(TTM)", "近五年每周样本由 Excel 公式计算分位"],
    ["Excel公式", "PERCENTRANK.INC", "计算近五年 PE 分位", "不调用 Wind MCP"],
  ]);
  styleHeader(sources.getRange("A1:D1"));
  setWidths(sources, [20, 48, 36, 60]);
  sources.showGridLines = false;

  for (const sheet of [summary, candidates, coverage, raw, universe, peWeekly, config, sources]) {
    sheet.getUsedRange(true).format.wrapText = true;
    sheet.getUsedRange(true).format.verticalAlignment = "top";
  }

  const previewRanges = {
    Summary: "A1:D9",
    Candidates: "A1:M25",
    "Index Coverage": "A1:M35",
    "Raw ETF + Wind": "A1:P35",
    Config: "A1:C8",
    Sources: "A1:D6",
  };
  for (const [sheetName, range] of Object.entries(previewRanges)) {
    const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
    await fs.writeFile(
      path.join(OUTPUT_DIR, `${sheetName.replace(/\s+/g, "_")}_formula_version.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(REPORT_PATH);
  await log("Wind Excel formula report completed", { output: REPORT_PATH });
  return REPORT_PATH;
}

buildWorkbook().catch(async (error) => {
  await log("Wind Excel formula report failed", { message: error.message, stack: error.stack });
  process.exitCode = 1;
});
