/* Shared presentation metadata; routes and permissions remain authoritative. */
export const PRIMARY_NAVIGATION = [
  { page: 'fingpt', glyph: 'chat', title: 'FinGPT', href: '#/fingpt' },
  { page: 'claw', glyph: 'layers', title: 'Claw', href: '#/claw' },
  { page: 'reports', glyph: 'document', title: '报告生产', href: '#/reports' },
  { page: 'market', glyph: 'globe', title: '全市场概览', href: '#/market' },
  { page: 'assets', glyph: 'candles', title: '资产观察', href: '#/assets' },
  { page: 'intel', glyph: 'radar', title: '研究情报', href: '#/intel/overview' },
  { page: 'aihot', glyph: 'newspaper', title: 'AI 资讯', href: '#/aihot/daily' },
  { page: 'frameworks', glyph: 'network', title: '研究框架', href: '#/frameworks' },
  { page: 'simulation', glyph: 'flask', title: '策略模拟', href: '#/simulation/etf' },
  { page: 'skills', glyph: 'grid', title: '能力中心', href: '#/skills' },
  { page: 'automations', glyph: 'calendarClock', title: '定时任务', href: '#/automations' },
  { page: 'operations', glyph: 'gauge', title: '运行与用量', href: '#/operations' },
];

export const settingsSections = Object.freeze([
  { id: 'general', label: '通用', eyebrow: 'GENERAL', description: '管理仅影响当前浏览器的显示偏好。' },
  { id: 'users', label: '用户管理', eyebrow: 'USER MANAGEMENT', description: '邀请用户，并管理账号和研究实例。', adminOnly: true },
  { id: 'model', label: '模型服务', eyebrow: 'MODEL SERVICE', description: '配置 Research Runtime 使用的模型服务。', refreshable: true },
  { id: 'data', label: '数据源', eyebrow: 'DATA CONNECTIONS', description: '管理专业数据源、API 数据源与公开来源。', refreshable: true },
  { id: 'local', label: '本机集成', eyebrow: 'LOCAL INTEGRATIONS', description: '诊断当前服务设备上的本机服务、文件夹、Office、浏览器与 MCP 能力。', refreshable: true },
  {id:'hot',label:'热点与事件',eyebrow:'HOT EVENTS',description:'配置持续采集、事件与频道的独立服务。'},
  { id: 'docs', label: '架构文档', eyebrow: 'DOCUMENTATION', description: '只读查看当前架构与实现说明。' },
]);

export const intelTabs = [
  ['timeline', '事件时间线'],
  ['overview', '事件总览'], ['research-reports', '研究报告'],
  ['investment-news', 'Investment News'], ['wsc', '见闻快讯'],
  ['social', '社交媒体监控'], ['events', '事件概率'],
];

export const assetTabs = [['assets', '行情与基本面', '#/assets'], ['funds', '基金数据', '#/assets/funds'], ['dossiers', '研究档案', '#/assets?view=dossiers']];
