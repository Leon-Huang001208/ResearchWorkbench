#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const outputDirectory = path.join(
  root,
  "docs/architecture/merged-platform/detailed/diagrams",
);

const domains = [
  {
    code: "D01",
    slug: "market",
    requestSlug: "market-request",
    stateSlug: "market-state",
    title: "全市场首页",
    page: "P01 · 全市场首页",
    api: "GET /api/market-home",
    sse: "GET /api/market-home/events",
    service: "MarketHomeService",
    repository: "MarketSnapshotRepository",
    store: "market_home_snapshot",
    capabilities: ["全球背景", "A股状态", "市场主线", "重要事件", "资产异动"],
    inputs: ["全球与A股行情", "验证事件", "交易日历"],
    transforms: ["交易时段判定", "同行百分位归一", "透明主线评分"],
    outputs: ["live 投影", "close 快照", "区块失效事件"],
    facts: ["as_of + source_refs", "fresh/stale/unavailable", "历史只读快照"],
    lifecycle: {
      title: "交易日与首页快照状态机",
      main: [
        ["pre_open", "盘前", "准备 live 投影"],
        ["open_am", "开盘", "30/60 秒刷新"],
        ["lunch", "午休", "保留上午状态"],
        ["open_pm", "午后开盘", "恢复 live 刷新"],
        ["closed", "收盘", "生成不可变快照"],
      ],
      alternatives: [
        ["non_trading", "非交易日", "只读最近快照", "neutral"],
        ["degraded", "数据降级", "stale / unavailable", "failure"],
      ],
    },
  },
  {
    code: "D02",
    slug: "theme",
    requestSlug: "theme-request",
    stateSlug: "pack-state",
    title: "主题研究 Pack",
    page: "P02 · 主题研究",
    api: "GET /api/theme-packs/{pack_key}/snapshot",
    sse: "Pack 刷新领域事件",
    service: "ThemePackService",
    repository: "ThemeObservationRepository",
    store: "theme_observation / theme_pack",
    capabilities: ["Pack 目录", "KPI 序列", "产业链", "关联资产", "数据健康"],
    inputs: ["Manifest", "供应商数据集", "验证事件"],
    transforms: ["normalize", "validate", "derive"],
    outputs: ["Theme Snapshot", "类型化读模型", "研究工作区入口"],
    facts: ["黄金/航天/光伏/AI", "统一 Observation", "插件禁止联网写库"],
    lifecycle: {
      title: "Research Pack 生命周期",
      main: [
        ["discovered", "已发现", "读取 Manifest"],
        ["validated", "已验证", "Schema + 来源检查"],
        ["enabled", "已启用", "生成读模型"],
        ["refreshed", "刷新中", "摄入 Observation"],
        ["ready", "可用", "发布 Snapshot"],
      ],
      alternatives: [
        ["degraded", "已降级", "部分事实不可用", "waiting"],
        ["disabled", "已禁用", "兼容或质量失败", "failure"],
      ],
    },
  },
  {
    code: "D03",
    slug: "asset",
    requestSlug: "alert-request",
    stateSlug: "alert-state",
    title: "资产观察与提醒",
    page: "P03/P06 · 资产观察与自选提醒",
    api: "GET /api/assets/{asset_id}",
    sse: "Alert 领域事件 → 通知收件箱",
    service: "AssetObservationService",
    repository: "AssetObservationRepository",
    store: "asset_registry / watchlist / alert_rule",
    capabilities: ["统一资产身份", "类型化详情", "同类比较", "Watchlist", "提醒与通知"],
    inputs: ["股票/指数/ETF/基金", "行情与净值", "公告与主题事件"],
    transforms: ["供应商代码映射", "peer-set 选择", "提醒条件评估"],
    outputs: ["AssetSnapshotEnvelope", "AlertEvent", "Inbox + 桌面通知"],
    facts: ["false→true 触发", "cooldown 去重", "过期数据跳过"],
    lifecycle: {
      title: "提醒规则求值状态机",
      main: [
        ["idle", "未满足", "等待新事实"],
        ["evaluating", "求值中", "读取最新事实"],
        ["triggered", "已触发", "false → true"],
        ["cooldown", "冷却中", "持续满足去重"],
        ["resolved", "已恢复", "条件回到 false"],
      ],
      alternatives: [
        ["stale", "跳过", "skipped_data_stale", "waiting"],
        ["disabled", "已停用", "用户关闭规则", "failure"],
      ],
    },
  },
  {
    code: "D04",
    slug: "fingpt",
    requestSlug: "fingpt-request",
    stateSlug: "fingpt-run",
    title: "FinGPT 即时研究",
    page: "P04 · FinGPT 研究工作区",
    api: "POST /api/research-runs",
    sse: "GET /api/research-runs/{run_id}/events",
    service: "ResearchRunService",
    repository: "ResearchRunRepository",
    store: "workspace / session / run / evidence",
    capabilities: ["统一输入", "会话研究", "证据与主张", "研究笔记", "后台运行"],
    inputs: ["文本/URL/PDF/图片", "工作区上下文", "检索范围"],
    transforms: ["输入路由", "检索与证据化", "质量门"],
    outputs: ["Claim + Evidence", "Artifact", "版本化 Note"],
    facts: ["LangGraph 回退", "SSE 可恢复", "可升级至 Claw"],
    lifecycle: {
      title: "FinGPT Research Run 状态机",
      main: [
        ["queued", "已排队", "持久化 Run"],
        ["retrieving", "检索中", "收集来源"],
        ["reasoning", "研究中", "生成 Claim"],
        ["quality", "质量门", "证据与引用检查"],
        ["completed", "已完成", "归档 Artifact"],
      ],
      alternatives: [
        ["blocked", "等待输入", "附件或范围缺失", "waiting"],
        ["cancelled", "已取消", "用户停止", "failure"],
      ],
    },
  },
  {
    code: "D05",
    slug: "claw",
    requestSlug: "claw-request",
    stateSlug: "claw-run",
    title: "Claw 多 Agent 研究",
    page: "P04 · Claw 多 Agent 控制台",
    api: "POST /api/research-runs (mode=claw)",
    sse: "Research Run SSE + Blackboard",
    service: "AgentOrchestrationService",
    repository: "ResearchRun / AgentTeam Repository",
    store: "agent_team / blackboard / research_run",
    capabilities: ["Supervisor", "Agent Team", "Shared Blackboard", "声明式 Skill", "预算与恢复"],
    inputs: ["复杂研究目标", "Team Definition", "Skill + MCP 白名单"],
    transforms: ["任务分解", "并发 Agent 执行", "Supervisor 汇总"],
    outputs: ["共享 Artifact", "Evidence/Claim", "预算与步骤审计"],
    facts: ["最大步骤/并发", "token/费用/截止时间", "blocked_runtime"],
    lifecycle: {
      title: "Claw 多 Agent Run 状态机",
      main: [
        ["queued", "已排队", "校验 Team"],
        ["planning", "编排中", "Supervisor 分解"],
        ["executing", "协作中", "Agent + Blackboard"],
        ["reviewing", "汇总中", "质量门"],
        ["completed", "已完成", "回写共享研究内核"],
      ],
      alternatives: [
        ["blocked_runtime", "运行时阻塞", "DSH 不可用", "waiting"],
        ["budget_exceeded", "预算终止", "达到硬限制", "failure"],
      ],
    },
  },
  {
    code: "D06",
    slug: "core",
    requestSlug: "schedule-request",
    stateSlug: "scheduled-job",
    title: "平台能力与调度内核",
    page: "P07/P08 · 能力日程与通知中心",
    api: "POST /api/agent-schedules",
    sse: "DomainEvent → Notification",
    service: "SchedulerCoordinator",
    repository: "PlatformRepository / ScheduledJobRepository",
    store: "runtime_provider / scheduled_job / domain_event",
    capabilities: ["Runtime Registry", "Skill 校验", "Scheduler", "领域事件", "持久化通知"],
    inputs: ["Provider 配置", "Skill Manifest", "Agent Schedule"],
    transforms: ["白名单校验", "租约领取", "错过运行合并"],
    outputs: ["DomainEvent", "Notification", "Tauri 系统通知"],
    facts: ["内部 Contract 非公共 API", "默认禁止重入", "收件箱优先持久化"],
    lifecycle: {
      title: "Scheduled Job 租约状态机",
      main: [
        ["scheduled", "已计划", "等待 next_run_at"],
        ["leased", "已租约", "唯一执行者"],
        ["running", "执行中", "发出领域命令"],
        ["persisting", "持久化", "写入结果与事件"],
        ["completed", "已完成", "计算下次运行"],
      ],
      alternatives: [
        ["coalesced", "已合并", "仅保留最近一次", "waiting"],
        ["failed", "失败待重试", "租约过期后恢复", "failure"],
      ],
    },
  },
];

function writeJson(fileName, value) {
  fs.mkdirSync(outputDirectory, { recursive: true });
  const target = path.join(outputDirectory, fileName);
  const temporary = `${target}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  fs.renameSync(temporary, target);
  process.stdout.write(`${JSON.stringify({ level: "info", event: "diagram_source_written", file: fileName })}\n`);
}

function views(prefix, focusGroups) {
  return focusGroups.map((focus, index) => ({
    id: `${prefix}-${index + 1}`,
    label: ["主链", "边界", "异常"][index],
    focus,
    note: ["按实施主链查看功能落点。", "查看模块所有权和通信边界。", "查看降级、阻塞或恢复分支。"][index],
  }));
}

function architectureMeta(title, output, guidedViews) {
  return {
    title,
    output,
    viewBox: [1320, 660],
    animation: "trace",
    quality_profile: "showcase",
    views: guidedViews,
  };
}

function buildCapabilities(domain) {
  const ids = domain.capabilities.map((_, index) => `cap${index + 1}`);
  const components = [
    { id: "user", type: "external", label: "研究者", sublabel: "单人本地优先", pos: [25, 290], size: [115, 62] },
    { id: "page", type: "frontend", label: domain.title, sublabel: "Web / Tauri 共用", pos: [180, 290], size: [155, 62] },
    ...domain.capabilities.map((label, index) => ({
      id: ids[index],
      type: index === 4 ? "security" : "backend",
      label,
      sublabel: `CAP · ${domain.code}-${String(index + 1).padStart(2, "0")}`,
      pos: [410, 55 + index * 115],
      size: [155, 62],
    })),
    { id: "service", type: "backend", label: "领域 Service", sublabel: domain.service, pos: [720, 290], size: [180, 62] },
    { id: "store", type: "database", label: "领域数据表", sublabel: domain.store, pos: [1030, 290], size: [205, 62] },
  ];
  return {
    schema_version: 1,
    diagram_type: "architecture",
    meta: architectureMeta(`${domain.code}-01 · ${domain.title}能力边界`, `${domain.code}-01-${domain.slug}-capabilities.html`, views(domain.slug, [["user", "page", ...ids, "service", "store"], ["page", "service", "store"], [ids[4], "service"]])),
    components,
    connections: [
      { from: "user", to: "page", label: "进入", variant: "emphasis" },
      ...ids.map((id, index) => ({ from: "page", to: id, variant: index === 0 ? "emphasis" : "default", fromSide: "right", toSide: "left" })),
      ...ids.map((id) => ({ from: id, to: "service", fromSide: "right", toSide: "left" })),
      { from: "service", to: "store", variant: "security" },
    ],
    cards: [
      { dot: "cyan", title: "页面职责", items: domain.capabilities.slice(0, 3) },
      { dot: "emerald", title: "服务边界", items: [domain.service, "模块间只经 Service/Contract", "数据表只由 Owner 访问"] },
      { dot: "rose", title: "禁止事项", items: ["页面不直连数据库", "事实缺失不用零值或模型猜测", "研究结果不写事实区"] },
    ],
  };
}

function buildInterfaces(domain) {
  return {
    schema_version: 1,
    diagram_type: "architecture",
    meta: architectureMeta(`${domain.code}-02 · ${domain.title}接口与服务`, `${domain.code}-02-${domain.slug}-interfaces.html`, views(`${domain.slug}-if`, [["page", "api", "service", "repo", "store"], ["contract", "service", "repo"], ["sse", "event", "page"]])),
    components: [
      { id: "page", type: "frontend", label: domain.title, sublabel: domain.page, pos: [35, 250], size: [190, 68] },
      { id: "api", type: "cloud", label: "HTTP 主接口", sublabel: domain.api, pos: [285, 150], size: [225, 68] },
      { id: "sse", type: "messagebus", label: "SSE / 异步事件", sublabel: domain.sse, pos: [285, 370], size: [225, 68] },
      { id: "contract", type: "security", label: "共享 Contract", sublabel: "ID / 来源 / 时间 / 质量", pos: [565, 60], size: [180, 68] },
      { id: "service", type: "backend", label: "领域 Service", sublabel: domain.service, pos: [565, 250], size: [180, 68] },
      { id: "event", type: "messagebus", label: "DomainEvent", sublabel: "事务后发布", pos: [565, 440], size: [180, 68] },
      { id: "repo", type: "backend", label: "领域 Repository", sublabel: domain.repository, pos: [825, 250], size: [205, 68] },
      { id: "store", type: "database", label: "领域数据表", sublabel: domain.store, pos: [1095, 250], size: [195, 68] },
    ],
    connections: [
      { from: "page", to: "api", label: "HTTP", variant: "emphasis" },
      { from: "api", to: "service", label: "调用" },
      { from: "contract", to: "api", variant: "security" },
      { from: "contract", to: "service", variant: "security" },
      { from: "service", to: "repo", label: "拥有" },
      { from: "repo", to: "store", label: "读/写", variant: "security" },
      { from: "service", to: "event" },
      { from: "event", to: "sse", label: "投影" },
      { from: "sse", to: "page", label: "失效/进度", variant: "dashed" },
    ],
    cards: [
      { dot: "emerald", title: "同步请求", items: [domain.api, "写接口要求 Idempotency-Key", "读模型明确 200/206 与错误码"] },
      { dot: "cyan", title: "异步通道", items: [domain.sse, "SSE 支持 Last-Event-ID", "客户端收到失效后重读聚合 API"] },
      { dot: "rose", title: "数据所有权", items: [domain.repository, domain.store, "其他模块不得直接访问本模块表"] },
    ],
  };
}

function buildSequence(domain) {
  return {
    schema_version: 1,
    diagram_type: "sequence",
    meta: {
      title: `${domain.code}-03 · ${domain.title}请求时序`,
      output: `${domain.code}-03-${domain.requestSlug}.html`,
      viewBox: [1600, 620],
      animation: "trace",
      visual_preset: "signal-flow",
      quality_profile: "showcase",
      column_fit: "spread",
      views: views(`${domain.slug}-seq`, [["user", "page", "api", "service", "store"], ["service", "event", "page"], ["service", "store", "page"]]),
    },
    participants: [
      { id: "user", type: "external", label: "研究者" },
      { id: "page", type: "frontend", label: domain.title },
      { id: "api", type: "cloud", label: "FastAPI" },
      { id: "service", type: "backend", label: "领域 Service" },
      { id: "store", type: "database", label: "PostgreSQL" },
      { id: "event", type: "messagebus", label: "SSE / Event" },
    ],
    segments: [
      { from: 145, to: 235, label: "接受与校验" },
      { from: 245, to: 375, label: "服务与持久化" },
      { from: 385, to: 510, label: "响应与增量状态" },
    ],
    messages: [
      { from: "user", to: "page", y: 160, label: "发起功能动作", variant: "emphasis" },
      { from: "page", to: "api", y: 190, label: domain.api, variant: "emphasis" },
      { from: "api", to: "service", y: 220, label: "校验 Contract + 权限" },
      { from: "service", to: "store", y: 255, label: "读取 Owned Data" },
      { from: "store", to: "service", y: 290, label: domain.facts[0], variant: "return" },
      { from: "service", to: "store", y: 325, label: "必要时幂等持久化", variant: "security" },
      { from: "service", to: "event", y: 360, label: domain.outputs[2], variant: "dashed" },
      { from: "service", to: "api", y: 395, label: "类型化响应 / 206 降级", variant: "return" },
      { from: "api", to: "page", y: 430, label: "读模型 + 状态", variant: "return" },
      { from: "event", to: "page", y: 465, label: domain.sse, variant: "dashed" },
      { from: "page", to: "user", y: 500, label: "刷新区块 / 展示异常", variant: "return" },
    ],
    activations: [
      { participant: "api", from: 185, to: 438, type: "cloud" },
      { participant: "service", from: 215, to: 403, type: "backend" },
      { participant: "store", from: 250, to: 333, type: "database" },
      { participant: "event", from: 355, to: 473, type: "messagebus" },
    ],
    cards: [
      { dot: "cyan", title: "请求入口", items: [domain.api, "请求模型先完成结构与语义校验", "写操作使用幂等键"] },
      { dot: "emerald", title: "服务执行", items: [domain.service, domain.repository, "只访问本模块拥有的数据"] },
      { dot: "rose", title: "异常与恢复", items: [domain.facts[1], "SSE 断线可重连", "错误状态必须可见，不伪造成功"] },
    ],
  };
}

function buildLifecycle(domain) {
  const mainStates = domain.lifecycle.main.map(([id, label, sublabel], index) => ({
    id,
    type: index === 0 ? "start" : index === 4 ? "success" : index === 3 ? "decision" : "active",
    label,
    sublabel,
    lane: "main",
    col: index,
    step: String(index + 1).padStart(2, "0"),
  }));
  const alternativeStates = domain.lifecycle.alternatives.map(([id, label, sublabel, type], index) => ({
    id,
    type,
    label,
    sublabel,
    lane: index === 0 ? "alternate" : "terminal",
    col: 2,
  }));
  return {
    schema_version: 1,
    diagram_type: "lifecycle",
    meta: {
      title: `${domain.code}-04 · ${domain.lifecycle.title}`,
      output: `${domain.code}-04-${domain.stateSlug}.html`,
      viewBox: [1800, 720],
      animation: "trace",
      quality_profile: "showcase",
      views: views(`${domain.slug}-life`, [mainStates.map((state) => state.id), [mainStates[2].id, alternativeStates[0].id], [alternativeStates[0].id, alternativeStates[1].id, mainStates[1].id]]),
    },
    lanes: [
      { id: "main", label: "主状态" },
      { id: "alternate", label: "等待或降级" },
      { id: "terminal", label: "终止或恢复" },
    ],
    states: [...mainStates, ...alternativeStates],
    transitions: [
      { from: mainStates[2].id, to: alternativeStates[0].id, variant: "security", route: "drop" },
      { from: alternativeStates[0].id, to: alternativeStates[1].id, variant: "security", route: "drop" },
    ],
    cards: [
      { dot: "emerald", title: "主路径", items: mainStates.map((state) => state.label) },
      { dot: "amber", title: "等待/降级", items: [alternativeStates[0].label, alternativeStates[0].sublabel, "不把等待态伪装成成功"] },
      { dot: "rose", title: "终止与恢复", items: [alternativeStates[1].label, alternativeStates[1].sublabel, "恢复必须回到明确活动态"] },
    ],
  };
}

function buildDataflow(domain) {
  return {
    schema_version: 1,
    diagram_type: "dataflow",
    meta: {
      title: `${domain.code}-05 · ${domain.title}事实数据流`,
      output: `${domain.code}-05-${domain.slug}-dataflow.html`,
      viewBox: [1600, 850],
      animation: "trace",
      quality_profile: "showcase",
      views: views(`${domain.slug}-data`, [["source", "normalize", "quality", "derive", "store", "read"], ["quality", "quarantine", "store"], ["store", "read", "event"]]),
    },
    stages: [
      { label: "来源" },
      { label: "标准化" },
      { label: "质量与计算" },
      { label: "事实存储" },
      { label: "读模型与事件" },
    ],
    nodes: [
      { id: "source", type: "cloud", label: domain.inputs[0], sublabel: domain.inputs[1], stage: 0, row: 1, tag: "SourceRef" },
      { id: "normalize", type: "backend", label: domain.transforms[0], sublabel: "统一 ID / 单位 / 时间", stage: 1, row: 1 },
      { id: "quality", type: "security", label: "质量门", sublabel: domain.facts[1], stage: 2, row: 1, tag: "QualityFlags" },
      { id: "derive", type: "backend", label: domain.transforms[2], sublabel: domain.transforms[1], stage: 3, row: 3 },
      { id: "quarantine", type: "messagebus", label: "隔离区", sublabel: "保留原值与原因", stage: 2, row: 4 },
      { id: "store", type: "database", label: "领域事实存储", sublabel: "Owned tables · PostgreSQL", stage: 3, row: 1, width: 160 },
      { id: "read", type: "frontend", label: "类型化读模型", sublabel: domain.outputs[0], stage: 4, row: 1, width: 144 },
      { id: "event", type: "messagebus", label: "领域事件", sublabel: domain.outputs[2], stage: 4, row: 3, width: 144 },
    ],
    flows: [
      { from: "source", to: "normalize", label: "观测", classification: "ObservationEnvelope", variant: "emphasis", route: "straight" },
      { from: "normalize", to: "quality", label: "标准化事实", classification: "typed", variant: "security", route: "straight" },
      { from: "quality", to: "store", label: "通过", variant: "emphasis", route: "straight", labelAt: [625, 210] },
      { from: "quality", to: "derive", label: "计算", route: "auto", fromSide: "right", toSide: "left", labelAt: [650, 430] },
      { from: "derive", to: "store", label: "派生", route: "vertical-channel", labelAt: [760, 405] },
      { from: "quality", to: "quarantine", label: "隔离", variant: "security", route: "vertical-channel", labelAt: [530, 455] },
      { from: "store", to: "read", label: "投影", variant: "emphasis", route: "straight", labelAt: [890, 210] },
      { from: "store", to: "event", label: "事件", variant: "dashed", route: "bottom-channel", labelAt: [885, 430] },
    ],
    cards: [
      { dot: "cyan", title: "统一事实语义", items: ["observed_at / available_at / as_of", "source_refs / freshness_status", "quality_flags 明确展示"] },
      { dot: "emerald", title: "可复现计算", items: domain.transforms },
      { dot: "rose", title: "质量边界", items: domain.facts },
    ],
  };
}

try {
  for (const domain of domains) {
    writeJson(`${domain.code}-01-${domain.slug}-capabilities.architecture.json`, buildCapabilities(domain));
    writeJson(`${domain.code}-02-${domain.slug}-interfaces.architecture.json`, buildInterfaces(domain));
    writeJson(`${domain.code}-03-${domain.requestSlug}.sequence.json`, buildSequence(domain));
    writeJson(`${domain.code}-04-${domain.stateSlug}.lifecycle.json`, buildLifecycle(domain));
    writeJson(`${domain.code}-05-${domain.slug}-dataflow.dataflow.json`, buildDataflow(domain));
  }
  process.stdout.write(`${JSON.stringify({ level: "info", event: "domain_diagram_sources_complete", count: domains.length * 5 })}\n`);
} catch (error) {
  process.stderr.write(`${JSON.stringify({ level: "error", event: "domain_diagram_sources_failed", message: error instanceof Error ? error.message : String(error) })}\n`);
  process.exitCode = 1;
}
