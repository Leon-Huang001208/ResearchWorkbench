import fs from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const execFileAsync = promisify(execFile);

const ROOT = "/Users/leon/Desktop/Projects/ResearchWorkbench";
const DEFAULT_INPUT = "/Users/leon/Desktop/公募基金_概况.xlsx";
const WIND_SKILL_DIR = path.join(ROOT, ".agents/skills/wind-mcp-skill");
const NODE_BIN = "/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node";
const OUTPUT_DIR = path.join(ROOT, "outputs/etf_gap_report_20260702");
const LOG_DIR = path.join(ROOT, "logs");

const args = new Map(
  process.argv.slice(2).map((arg) => {
    const [key, ...rest] = arg.replace(/^--/, "").split("=");
    return [key, rest.join("=") || "true"];
  }),
);

const inputPath = args.get("input") || DEFAULT_INPUT;
const refresh = args.has("refresh");
const offlineFundInfo = args.has("offline-fund-info");
const offlineIndexPe = args.has("offline-index-pe");
const runId = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "");
const cacheDir = path.join(OUTPUT_DIR, "wind_cache");
const logPath = path.join(LOG_DIR, `etf_gap_report_${runId}.log`);
const reportPath = path.join(OUTPUT_DIR, "华安基金ETF缺口与指数近五年PE分位报告.xlsx");

async function log(message, payload = null) {
  const line = `${new Date().toISOString()} ${message}${payload ? ` ${JSON.stringify(payload)}` : ""}\n`;
  await fs.appendFile(logPath, line, "utf8");
  console.log(message);
}

function chunk(items, size) {
  const chunks = [];
  for (let i = 0; i < items.length; i += size) chunks.push(items.slice(i, i + size));
  return chunks;
}

function toNumber(value) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (value === null || value === undefined || value === "" || value === "--") return null;
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeName(value) {
  return String(value || "")
    .replace(/\s+/g, "")
    .replace(/指数$/g, "")
    .replace(/[（）]/g, (char) => (char === "（" ? "(" : ")"))
    .trim();
}

function fallbackIndexName(fundName) {
  let name = String(fundName || "").trim();
  name = name.replace(/交易型开放式指数证券投资基金.*/, "");
  name = name.replace(/交易型开放式证券投资基金.*/, "");
  name = name.replace(/ETF联接.*/, "");
  name = name.replace(/ETF$/, "");
  name = name.replace(/增强策略$/, "");
  name = name.replace(/增强$/, "");
  name = name.replace(/^(鹏扬|鹏华|华夏|易方达|富国|南方|汇添富|广发|国泰|华泰柏瑞|嘉实|博时|招商|华宝|华安|银华|工银瑞信|天弘|平安|景顺长城|万家|建信|摩根|海富通|国联安|大成|申万菱信|兴业|国寿安保|泰康|华富|浦银安盛|中银|农银汇理|前海开源|西部利得|华泰保兴|中金|华商|东财|方正富邦|财通|国联|华润元大|永赢|长盛|长城|华西|新华|民生加银|汇安|中信保诚|安信|华泰紫金|光大保德信|国投瑞银|摩根士丹利|国金|中欧|华富|华宸未来)/, "");
  return name || "";
}

function parseWindPayload(stdout) {
  const outer = JSON.parse(stdout);
  if (outer.isError) throw new Error(`Wind returned isError: ${stdout.slice(0, 800)}`);
  const text = outer?.content?.[0]?.text;
  if (!text) throw new Error(`Wind response missing content text: ${stdout.slice(0, 800)}`);
  const inner = JSON.parse(text);
  if (inner.error) throw new Error(`Wind data error: ${JSON.stringify(inner.error)}`);
  return inner?.data?.data || [];
}

function tableRows(step) {
  const columns = (step.columns || []).map((col) => col.name);
  return (step.rows || []).map((row) => Object.fromEntries(columns.map((name, index) => [name, row[index]])));
}

function firstByColumnPattern(row, patterns) {
  for (const [name, value] of Object.entries(row)) {
    if (patterns.every((pattern) => pattern.test(name))) return value;
  }
  return undefined;
}

async function callWind(serverType, toolName, params, cacheKey) {
  const cachePath = path.join(cacheDir, `${cacheKey}.json`);
  if (!refresh) {
    try {
      const cached = await fs.readFile(cachePath, "utf8");
      await log(`Using cached Wind response: ${cacheKey}`);
      return JSON.parse(cached);
    } catch {
      // Cache miss is expected on first run.
    }
  }

  const paramsJson = JSON.stringify(params);
  try {
    const { stdout, stderr } = await execFileAsync(
      NODE_BIN,
      ["scripts/cli.mjs", "call", serverType, toolName, paramsJson],
      { cwd: WIND_SKILL_DIR, maxBuffer: 1024 * 1024 * 20, timeout: 120000 },
    );
    if (stderr) await log(`Wind stderr for ${cacheKey}`, { stderr: stderr.slice(0, 1000) });
    const parsed = parseWindPayload(stdout);
    await fs.writeFile(cachePath, JSON.stringify(parsed, null, 2), "utf8");
    await log(`Fetched Wind response: ${cacheKey}`);
    return parsed;
  } catch (error) {
    await log(`Wind call failed: ${cacheKey}`, {
      message: error.message,
      stdout: error.stdout?.slice?.(0, 1200),
      stderr: error.stderr?.slice?.(0, 1200),
    });
    throw error;
  }
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

async function fetchFundInfo(etfs) {
  const result = new Map();
  const codeChunks = chunk(
    [...new Set(etfs.map((row) => String(row["基金代码"]).trim()).filter(Boolean))],
    10,
  );

  async function fetchCodes(codes, cachePrefix) {
    const cacheKey = `fund_info_${cachePrefix}_${codes[0]}_${codes.at(-1)}`.replace(/[^\w.-]/g, "_");
    if (offlineFundInfo) {
      const cachePath = path.join(cacheDir, `${cacheKey}.json`);
      try {
        const cached = await fs.readFile(cachePath, "utf8");
        await log(`Using cached Wind response: ${cacheKey}`);
        return JSON.parse(cached);
      } catch {
        if (codes.length === 1) {
          await log("Skipping uncached fund info single code in offline mode", { code: codes[0] });
          return [];
        }
        const midpoint = Math.ceil(codes.length / 2);
        await log("Splitting uncached fund info chunk in offline mode", { size: codes.length, first: codes[0], last: codes.at(-1) });
        const left = await fetchCodes(codes.slice(0, midpoint), `${cachePrefix}_a`);
        const right = await fetchCodes(codes.slice(midpoint), `${cachePrefix}_b`);
        return [...left, ...right];
      }
    }
    try {
      return await callWind(
      "fund_data",
      "get_fund_info",
      {
        question: `返回以下ETF基金的基金代码、基金名称、管理人、跟踪指数名称：${codes.join("、")}`,
      },
        cacheKey,
      );
    } catch (error) {
      if (codes.length === 1) {
        await log("Skipping fund info after single-code failure", { code: codes[0], message: error.message });
        return [];
      }
      const midpoint = Math.ceil(codes.length / 2);
      await log("Splitting fund info chunk after failure", { size: codes.length, first: codes[0], last: codes.at(-1) });
      const left = await fetchCodes(codes.slice(0, midpoint), `${cachePrefix}_a`);
      const right = await fetchCodes(codes.slice(midpoint), `${cachePrefix}_b`);
      return [...left, ...right];
    }
  }

  for (let index = 0; index < codeChunks.length; index += 1) {
    const codes = codeChunks[index];
    const steps = await fetchCodes(codes, index + 1);
    for (const step of steps) {
      for (const row of tableRows(step)) {
        const code = String(row["Wind代码"] || "").trim();
        if (code) result.set(code, row);
      }
    }
    await log(`Fund info progress ${index + 1}/${codeChunks.length}`, { rows: result.size });
  }

  return result;
}

async function fetchIndexFundamentals(indexNames) {
  const resultByName = new Map();
  const cleanNames = [...new Set(indexNames.map((name) => String(name || "").trim()).filter(Boolean))];
  const nameChunks = chunk(cleanNames, 12);

  async function fetchNames(names, cachePrefix) {
    const cacheKey = `index_5y_pe_${cachePrefix}_${normalizeName(names[0])}_${normalizeName(names.at(-1))}`.replace(/[^\w.-]/g, "_");
    if (offlineIndexPe) {
      const cachePath = path.join(cacheDir, `${cacheKey}.json`);
      try {
        const cached = await fs.readFile(cachePath, "utf8");
        await log(`Using cached Wind response: ${cacheKey}`);
        return JSON.parse(cached);
      } catch {
        await log("Skipping uncached index PE chunk in offline mode", { first: names[0], last: names.at(-1), size: names.length });
        return [];
      }
    }
    try {
      return await callWind(
      "index_data",
      "get_index_fundamentals",
      {
        question: `返回以下指数最新市盈率TTM和近五年市盈率TTM历史分位数：${names.join("、")}`,
      },
        cacheKey,
      );
    } catch (error) {
      if (names.length === 1) {
        await log("Skipping index PE after single-name failure", { indexName: names[0], message: error.message });
        return [];
      }
      const midpoint = Math.ceil(names.length / 2);
      await log("Splitting index PE chunk after failure", { size: names.length, first: names[0], last: names.at(-1) });
      const left = await fetchNames(names.slice(0, midpoint), `${cachePrefix}_a`);
      const right = await fetchNames(names.slice(midpoint), `${cachePrefix}_b`);
      return [...left, ...right];
    }
  }

  for (let index = 0; index < nameChunks.length; index += 1) {
    const names = nameChunks[index];
    const steps = await fetchNames(names, index + 1);

    for (const step of steps) {
      for (const row of tableRows(step)) {
        const key = normalizeName(row["证券简称"]);
        if (!key) continue;
        const existing = resultByName.get(key) || {};
        const merged = {
          ...existing,
          indexCode: row["Wind代码"] ?? existing.indexCode,
          indexShortName: row["证券简称"] ?? existing.indexShortName,
          releaseDate: row["发布日期"] ?? existing.releaseDate,
          valuationDate: row["日期"] ?? existing.valuationDate,
        };
        const fiveYearPe = firstByColumnPattern(row, [/近(5|五)年/, /市盈率/]);
        const fiveYearPercentile = firstByColumnPattern(row, [/近(5|五)年/, /市盈率/, /分位/]);
        const fiveYearRank = firstByColumnPattern(row, [/近(5|五)年/, /市盈率/, /序号/]);
        const fiveYearMaxRank = firstByColumnPattern(row, [/近(5|五)年/, /市盈率/, /最大序号/]);
        if (row["最新市盈率"] !== undefined) merged.peTtm = toNumber(row["最新市盈率"]);
        if (fiveYearPe !== undefined && merged.peTtm === undefined) {
          merged.peTtm = toNumber(fiveYearPe);
        }
        if (fiveYearPercentile !== undefined) {
          merged.pePercentileFiveYear = toNumber(fiveYearPercentile);
        }
        if (fiveYearRank !== undefined) merged.peRankFiveYear = toNumber(fiveYearRank);
        if (fiveYearMaxRank !== undefined) merged.peMaxRankFiveYear = toNumber(fiveYearMaxRank);
        resultByName.set(key, merged);
      }
    }
    await log(`Index PE progress ${index + 1}/${nameChunks.length}`, { rows: resultByName.size });
  }

  return resultByName;
}

function buildDataset(etfs, fundInfo, indexFundamentals) {
  const enriched = etfs.map((row) => {
    const code = String(row["基金代码"]).trim();
    const info = fundInfo.get(code) || {};
    const trackedIndex = String(info["跟踪指数名称"] || fallbackIndexName(row["基金名称"])).trim();
    const managerInput = String(row["管理人"] || "").trim();
    const managerWind = String(info["基金管理人"] || "").trim();
    const indexData = indexFundamentals.get(normalizeName(trackedIndex)) || {};
    return {
      code,
      fundName: row["基金名称"],
      fundType: row["类型"],
      ytdReturn: toNumber(row["年初至今收益率(%)"]),
      ytdRank: row["年初至今同类排名"],
      maxDrawdownYtd: toNumber(row["年初至今最大回撤(%)"]),
      scale: toNumber(row["规模(亿)"]),
      ageYears: toNumber(row["成立年限"]),
      fundManager: row["基金经理"],
      managerInput,
      rating: row["Wind3年评级"],
      windFundName: info["证券简称"] || "",
      managerWind,
      trackedIndex,
      trackingSource: info["跟踪指数名称"] ? "Wind基金档案" : "基金名称解析",
      isHuaAn: managerInput.includes("华安") || managerWind.includes("华安基金"),
      indexCode: indexData.indexCode || "",
      indexShortName: indexData.indexShortName || "",
      releaseDate: indexData.releaseDate || "",
      valuationDate: indexData.valuationDate || "",
      peTtm: indexData.peTtm ?? null,
      pePercentileSinceLaunch: indexData.pePercentileSinceLaunch ?? null,
      pePercentileTenYear: indexData.pePercentileTenYear ?? null,
      peRankSinceLaunch: indexData.peRankSinceLaunch ?? null,
      peMaxRankSinceLaunch: indexData.peMaxRankSinceLaunch ?? null,
    };
  });

  const byIndex = new Map();
  for (const row of enriched) {
    if (!row.trackedIndex) continue;
    const key = normalizeName(row.trackedIndex);
    if (!byIndex.has(key)) byIndex.set(key, []);
    byIndex.get(key).push(row);
  }

  const coverage = [...byIndex.entries()].map(([key, rows]) => {
    const sorted = [...rows].sort((a, b) => (b.scale || 0) - (a.scale || 0));
    const firstWithPe = rows.find((row) => row.indexCode || row.pePercentileSinceLaunch !== null) || {};
    const huaAnRows = rows.filter((row) => row.isHuaAn);
    const managers = [...new Set(rows.map((row) => row.managerInput || row.managerWind).filter(Boolean))].sort();
    const totalScale = rows.reduce((sum, row) => sum + (row.scale || 0), 0);
    return {
      key,
      trackedIndex: rows[0].trackedIndex,
      hasHuaAn: huaAnRows.length > 0,
      huaAnProducts: huaAnRows.map((row) => `${row.code} ${row.fundName}`).join("；"),
      productCount: rows.length,
      totalScale,
      managers: managers.join("；"),
      largestCode: sorted[0]?.code || "",
      largestFund: sorted[0]?.fundName || "",
      largestManager: sorted[0]?.managerInput || sorted[0]?.managerWind || "",
      largestScale: sorted[0]?.scale ?? null,
      representativeProducts: sorted.slice(0, 5).map((row) => `${row.code} ${row.fundName}`).join("；"),
      indexCode: firstWithPe.indexCode || "",
      indexShortName: firstWithPe.indexShortName || "",
      releaseDate: firstWithPe.releaseDate || "",
      valuationDate: firstWithPe.valuationDate || "",
      peTtm: firstWithPe.peTtm ?? null,
      pePercentileSinceLaunch: firstWithPe.pePercentileSinceLaunch ?? null,
      pePercentileTenYear: firstWithPe.pePercentileTenYear ?? null,
      peDataStatus: firstWithPe.pePercentileSinceLaunch === null || firstWithPe.pePercentileSinceLaunch === undefined ? "无PE分位数据" : "有PE分位数据",
    };
  });

  const opportunities = coverage
    .filter((row) => !row.hasHuaAn && row.pePercentileSinceLaunch !== null && row.pePercentileSinceLaunch < 0.9)
    .sort((a, b) => (a.pePercentileSinceLaunch ?? 9) - (b.pePercentileSinceLaunch ?? 9) || b.totalScale - a.totalScale);

  return { enriched, coverage, opportunities };
}

function writeMatrix(sheet, address, rows) {
  if (!rows.length) return;
  const range = sheet.getRangeByIndexes(address.row, address.col, rows.length, rows[0].length);
  range.values = rows;
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

function asPercent(value) {
  return value === null || value === undefined ? "" : value;
}

async function createReport(sourceMeta, dataset) {
  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("Summary");
  const opp = workbook.worksheets.add("Opportunities");
  const coverage = workbook.worksheets.add("All Index Coverage");
  const raw = workbook.worksheets.add("Raw ETF Data");
  const checks = workbook.worksheets.add("Checks");
  const sources = workbook.worksheets.add("Sources");

  const asOf = new Date().toISOString().slice(0, 10);
  const huaAnIndexes = dataset.coverage.filter((row) => row.hasHuaAn).length;
  const noHuaAnIndexes = dataset.coverage.length - huaAnIndexes;
  const peCoverage = dataset.coverage.filter((row) => row.pePercentileSinceLaunch !== null).length;
  const summaryRows = [
    ["华安基金ETF缺口与指数PE分位报告", "", "", ""],
    ["生成日期", asOf, "原始工作表", sourceMeta.sheetName],
    ["原始ETF数量", dataset.enriched.length, "华安ETF数量", dataset.enriched.filter((row) => row.isHuaAn).length],
    ["唯一跟踪指数数", dataset.coverage.length, "华安已覆盖指数数", huaAnIndexes],
    ["华安未覆盖指数数", noHuaAnIndexes, "有PE分位数据指数数", peCoverage],
    ["候选指数数（华安未覆盖且上市以来PE分位<90%）", dataset.opportunities.length, "估值口径", "Wind：上市以来PE(TTM)历史分位"],
    ["PE取数模式", offlineIndexPe ? "使用已缓存PE数据（Wind额度不足后生成）" : "实时调用Wind并缓存", "PE覆盖率", `${peCoverage}/${dataset.coverage.length}`],
    ["筛选逻辑", "全市场ETF跟踪指数 - 华安已覆盖指数；再保留上市以来PE(TTM)历史分位 < 90%。", "", ""],
    ["动态更新", "重新运行 reports/etf_gap_report/build_etf_gap_report.mjs 会读取最新Excel并重新调用Wind生成报告。", "", ""],
    ["", "", "", ""],
    ["Top候选指数", "上市以来PE分位", "现有ETF总规模(亿)", "最大ETF"],
    ...dataset.opportunities.slice(0, 12).map((row) => [
      row.trackedIndex,
      asPercent(row.pePercentileSinceLaunch),
      row.totalScale,
      `${row.largestCode} ${row.largestFund}`,
    ]),
  ];
  writeMatrix(summary, { row: 0, col: 0 }, summaryRows);
  summary.getRange("A1:D1").merge();
  summary.getRange("A1:D1").format = { fill: "#12343B", font: { bold: true, color: "#FFFFFF", size: 16 } };
  summary.getRange("A2:D9").format.borders = { preset: "inside", style: "thin", color: "#C8D3D8" };
  styleHeader(summary.getRange("A11:D11"));
  summary.getRange("B12:B23").format.numberFormat = "0.0%";
  summary.getRange("C12:C23").format.numberFormat = "#,##0.0";
  setWidths(summary, [34, 18, 20, 60]);
  summary.showGridLines = false;

  const oppHeaders = [
    "跟踪指数",
    "指数代码",
    "PE(TTM)",
    "上市以来PE分位",
    "近10年PE分位",
    "指数发布日期",
    "估值日期",
    "现有ETF数量",
    "现有ETF总规模(亿)",
    "最大ETF代码",
    "最大ETF名称",
    "最大ETF管理人",
    "最大ETF规模(亿)",
    "竞品管理人",
    "代表ETF产品",
    "筛选说明",
  ];
  const oppRows = [
    oppHeaders,
    ...dataset.opportunities.map((row) => [
      row.trackedIndex,
      row.indexCode,
      row.peTtm,
      asPercent(row.pePercentileSinceLaunch),
      asPercent(row.pePercentileTenYear),
      row.releaseDate,
      row.valuationDate,
      row.productCount,
      row.totalScale,
      row.largestCode,
      row.largestFund,
      row.largestManager,
      row.largestScale,
      row.managers,
      row.representativeProducts,
      "华安未覆盖；上市以来PE(TTM)历史分位低于90%",
    ]),
  ];
  writeMatrix(opp, { row: 0, col: 0 }, oppRows);
  styleHeader(opp.getRangeByIndexes(0, 0, 1, oppHeaders.length));
  if (oppRows.length > 1) {
    opp.tables.add(`A1:P${oppRows.length}`, true, "OpportunitiesTable");
    opp.getRange(`C2:C${oppRows.length}`).format.numberFormat = "#,##0.0";
    opp.getRange(`D2:E${oppRows.length}`).format.numberFormat = "0.0%";
    opp.getRange(`I2:I${oppRows.length}`).format.numberFormat = "#,##0.0";
    opp.getRange(`M2:M${oppRows.length}`).format.numberFormat = "#,##0.0";
    opp.getRange(`D2:D${oppRows.length}`).conditionalFormats.add("colorScale", {
      criteria: [
        { type: "lowestValue", color: "#D9F0E3" },
        { type: "percentile", value: 50, color: "#FFF3B0" },
        { type: "highestValue", color: "#F6C1B3" },
      ],
    });
  }
  opp.freezePanes.freezeRows(1);
  setWidths(opp, [22, 14, 12, 14, 14, 14, 12, 12, 16, 14, 34, 18, 16, 45, 70, 34]);
  opp.showGridLines = false;

  const coverageHeaders = [
    "跟踪指数",
    "华安是否覆盖",
    "华安产品",
    "现有ETF数量",
    "现有ETF总规模(亿)",
    "竞品管理人",
    "最大ETF",
    "指数代码",
    "PE(TTM)",
    "上市以来PE分位",
    "近10年PE分位",
    "估值日期",
    "PE数据状态",
    "代表ETF产品",
  ];
  const coverageRows = [
    coverageHeaders,
    ...dataset.coverage
      .sort((a, b) => Number(a.hasHuaAn) - Number(b.hasHuaAn) || (a.pePercentileSinceLaunch ?? 9) - (b.pePercentileSinceLaunch ?? 9))
      .map((row) => [
        row.trackedIndex,
        row.hasHuaAn ? "是" : "否",
        row.huaAnProducts,
        row.productCount,
        row.totalScale,
        row.managers,
        `${row.largestCode} ${row.largestFund}`,
        row.indexCode,
        row.peTtm,
        asPercent(row.pePercentileSinceLaunch),
        asPercent(row.pePercentileTenYear),
        row.valuationDate,
        row.peDataStatus,
        row.representativeProducts,
      ]),
  ];
  writeMatrix(coverage, { row: 0, col: 0 }, coverageRows);
  styleHeader(coverage.getRangeByIndexes(0, 0, 1, coverageHeaders.length));
  coverage.tables.add(`A1:N${coverageRows.length}`, true, "CoverageTable");
  coverage.getRange(`E2:E${coverageRows.length}`).format.numberFormat = "#,##0.0";
  coverage.getRange(`I2:I${coverageRows.length}`).format.numberFormat = "#,##0.0";
  coverage.getRange(`J2:K${coverageRows.length}`).format.numberFormat = "0.0%";
  coverage.freezePanes.freezeRows(1);
  setWidths(coverage, [24, 12, 48, 12, 16, 48, 52, 14, 12, 14, 14, 12, 16, 70]);
  coverage.showGridLines = false;

  const rawHeaders = [
    "基金代码",
    "基金名称",
    "管理人",
    "Wind管理人",
    "跟踪指数",
    "跟踪指数来源",
    "华安产品",
    "规模(亿)",
    "年初至今收益率(%)",
    "年初至今最大回撤(%)",
    "基金经理",
    "指数代码",
    "PE(TTM)",
    "上市以来PE分位",
    "近10年PE分位",
    "估值日期",
  ];
  const rawRows = [
    rawHeaders,
    ...dataset.enriched.map((row) => [
      row.code,
      row.fundName,
      row.managerInput,
      row.managerWind,
      row.trackedIndex,
      row.trackingSource,
      row.isHuaAn ? "是" : "否",
      row.scale,
      row.ytdReturn === null ? "" : row.ytdReturn / 100,
      row.maxDrawdownYtd === null ? "" : row.maxDrawdownYtd / 100,
      row.fundManager,
      row.indexCode,
      row.peTtm,
      asPercent(row.pePercentileSinceLaunch),
      asPercent(row.pePercentileTenYear),
      row.valuationDate,
    ]),
  ];
  writeMatrix(raw, { row: 0, col: 0 }, rawRows);
  styleHeader(raw.getRangeByIndexes(0, 0, 1, rawHeaders.length));
  raw.tables.add(`A1:P${rawRows.length}`, true, "RawETFTable");
  raw.getRange(`H2:H${rawRows.length}`).format.numberFormat = "#,##0.0";
  raw.getRange(`I2:J${rawRows.length}`).format.numberFormat = "0.0%";
  raw.getRange(`M2:M${rawRows.length}`).format.numberFormat = "#,##0.0";
  raw.getRange(`N2:O${rawRows.length}`).format.numberFormat = "0.0%";
  raw.freezePanes.freezeRows(1);
  setWidths(raw, [14, 34, 16, 24, 22, 14, 10, 12, 16, 16, 22, 14, 12, 14, 14, 12]);
  raw.showGridLines = false;

  const checksRows = [
    ["检查项", "状态", "结果", "备注"],
    ["原始ETF行数", "OK", dataset.enriched.length, "已跳过空基金代码/名称行"],
    ["Wind基金档案覆盖", dataset.enriched.every((row) => row.trackingSource === "Wind基金档案") ? "OK" : "WARN", dataset.enriched.filter((row) => row.trackingSource === "Wind基金档案").length, "未覆盖项使用基金名称解析"],
    ["指数PE分位覆盖", peCoverage > 0 ? (offlineIndexPe ? "WARN" : "OK") : "WARN", `${peCoverage}/${dataset.coverage.length}`, offlineIndexPe ? "Wind额度不足后使用缓存数据生成；无PE数据的指数未进入候选清单" : "无PE数据的指数未进入候选清单"],
    ["候选筛选阈值", "OK", "<90%", "基于上市以来PE(TTM)历史分位"],
    ["报告日志", "OK", logPath, "用于追溯Wind调用和失败信息"],
  ];
  writeMatrix(checks, { row: 0, col: 0 }, checksRows);
  styleHeader(checks.getRange("A1:D1"));
  checks.tables.add(`A1:D${checksRows.length}`, true, "ChecksTable");
  setWidths(checks, [24, 12, 55, 50]);
  checks.showGridLines = false;

  const sourcesRows = [
    ["来源类型", "来源", "用途", "备注"],
    ["本地Excel", inputPath, "ETF产品清单", "用户提供"],
    ["Wind fund_data.get_fund_info", "Wind金融数据服务", "基金档案、跟踪指数名称", "分块查询，结果缓存于输出目录 wind_cache"],
    ["Wind index_data.get_index_fundamentals", "Wind金融数据服务", "指数PE(TTM)、上市以来/近10年PE历史分位", offlineIndexPe ? "本次使用已缓存PE响应生成；额度恢复后可去掉 --offline-index-pe 重新刷新" : "估值日期见各数据表"],
    ["生成脚本", path.join(ROOT, "reports/etf_gap_report/build_etf_gap_report.mjs"), "动态更新", "重新运行即可基于新Excel和Wind最新数据再生成"],
  ];
  writeMatrix(sources, { row: 0, col: 0 }, sourcesRows);
  styleHeader(sources.getRange("A1:D1"));
  sources.tables.add(`A1:D${sourcesRows.length}`, true, "SourcesTable");
  setWidths(sources, [26, 80, 36, 60]);
  sources.showGridLines = false;

  for (const sheet of [summary, opp, coverage, raw, checks, sources]) {
    sheet.getUsedRange(true).format.wrapText = true;
    sheet.getUsedRange(true).format.verticalAlignment = "top";
  }

  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const previewRanges = {
    Summary: "A1:D24",
    Opportunities: `A1:P${Math.min(60, oppRows.length)}`,
    "All Index Coverage": `A1:N${Math.min(60, coverageRows.length)}`,
    "Raw ETF Data": `A1:P${Math.min(60, rawRows.length)}`,
    Checks: `A1:D${checksRows.length}`,
    Sources: `A1:D${sourcesRows.length}`,
  };
  for (const [sheetName, range] of Object.entries(previewRanges)) {
    const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
    await fs.writeFile(
      path.join(OUTPUT_DIR, `${sheetName.replace(/\s+/g, "_")}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
  });
  await log("Formula error scan", { ndjson: errors.ndjson });

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(reportPath);
  return reportPath;
}

async function main() {
  await fs.mkdir(LOG_DIR, { recursive: true });
  await fs.mkdir(cacheDir, { recursive: true });
  await log("ETF gap report run started", { inputPath, refresh });

  const source = await readSourceWorkbook();
  await log("Read source workbook", { sheetName: source.sheetName, rows: source.rows.length });
  const fundInfo = await fetchFundInfo(source.rows);
  const preliminary = source.rows.map((row) => {
    const code = String(row["基金代码"]).trim();
    const info = fundInfo.get(code) || {};
    return String(info["跟踪指数名称"] || fallbackIndexName(row["基金名称"])).trim();
  });
  await log("Prepared tracked index universe", { uniqueIndexes: new Set(preliminary.filter(Boolean).map(normalizeName)).size });
  const indexFundamentals = await fetchIndexFundamentals(preliminary);
  const dataset = buildDataset(source.rows, fundInfo, indexFundamentals);
  await log("Built dataset", {
    etfs: dataset.enriched.length,
    indexes: dataset.coverage.length,
    opportunities: dataset.opportunities.length,
  });
  const output = await createReport({ sheetName: source.sheetName }, dataset);
  await log("ETF gap report run completed", { output });
  console.log(output);
}

main().catch(async (error) => {
  await log("ETF gap report run failed", { message: error.message, stack: error.stack });
  process.exitCode = 1;
});
