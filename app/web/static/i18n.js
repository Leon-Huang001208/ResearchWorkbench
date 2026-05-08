/* ============================================================
   AlphaFoundry — Internationalization (i18n)
   ============================================================ */

const I18N = (() => {
    'use strict';

    // ─── Translation Dictionaries ────────────────────────────
    const zh = {
        // Brand / Global
        'brand': 'AlphaFoundry',
        'search.placeholder': '搜索实体、事件、信号...',

        // Navigation
        'nav.dashboard': '仪表盘',
        'nav.explorer': '资源管理器',
        'settings.title': '设置',
        'settings.theme': '外观',
        'settings.language': '语言',
        'settings.color_scheme': '颜色',
        'nav.asset-analysis': '资产分析',
        'nav.scenario': '情景分析',
        'nav.event-signal': '事件信号',
        'nav.industry-chain': '产业链',
        'nav.review': '审核队列',
        'nav.signals': '信号管理',
        'nav.ingest': '文档摄入',
        'nav.memory': '记忆与学习',

        // Dashboard
        'dashboard.title': '仪表盘',
        'dashboard.total_signals': '总信号数',
        'dashboard.research': '研究中',
        'dashboard.candidate': '候选信号',
        'dashboard.paper_trade': '模拟交易',
        'dashboard.pending_review': '待审核断言',
        'dashboard.recent_events': '最近事件',
        'dashboard.recent_reports': '最近报告',
        'dashboard.no_data': '暂无数据',

        // Asset Analysis
        'asset.title': '资产分析',
        'asset.code_placeholder': '输入资产代码，如 600000.SH',
        'asset.source_mock': 'Mock 数据',
        'asset.source_local': '本地数据',
        'asset.source_ifind': 'iFinD',
        'asset.btn_analyze': '分析',
        'asset.loading': '正在分析资产...',
        'asset.valuation': '估值',
        'asset.fund_flow': '资金流向',
        'asset.price_volume': '量价走势',
        'asset.financial': '财务数据',
        'asset.shareholder': '股东',
        'asset.industry': '产业',
        'asset.event_impact': '事件影响',
        'asset.macro': '宏观',
        'asset.no_data': '暂无数据',
        'asset.no_financial': '暂无财务数据',
        'asset.no_fund_flow': '暂无资金流向数据',
        'asset.no_shareholder': '暂无股东数据',
        'asset.no_industry': '暂无产业数据',
        'asset.no_event_impact': '暂无事件影响',
        'asset.no_macro': '暂无宏观数据',

        // Asset Metrics
        'metric.pe_ttm': 'PE (TTM)',
        'metric.pb': 'PB',
        'metric.ps': 'PS',
        'metric.ev_ebitda': 'EV/EBITDA',
        'metric.revenue': '营业收入 (Revenue)',
        'metric.net_profit': '净利润 (Net Profit)',
        'metric.eps': '每股收益 (EPS)',
        'metric.roe': '净资产收益率 (ROE)',
        'metric.main_net_inflow': '主力净流入',
        'metric.institutional_holding': '机构持仓',
        'metric.northbound_holding': '北向持仓',
        'metric.close_price': '收盘价',

        // Scenario
        'scenario.title': '情景分析',
        'scenario.topic_placeholder': '输入研究主题，如 人工智能产业发展',
        'scenario.subjects_placeholder': '关联标的（可选，逗号分隔）',
        'scenario.btn_generate': '生成情景',
        'scenario.loading': '正在生成情景分析...',
        'scenario.prob_chart': '情景概率分布',
        'scenario.residual': '残余不确定性',
        'scenario.narrative': '叙述',
        'scenario.implications': '市场含义',
        'scenario.key_drivers': '关键驱动',
        'scenario.probability': '概率',

        // Event Signal
        'event.title': '事件信号',
        'event.trigger': '触发事件信号',
        'event.event_title': '事件标题',
        'event.event_title_placeholder': '事件标题',
        'event.event_type': '事件类型',
        'event.type_earnings': '财报',
        'event.type_policy': '政策',
        'event.type_product': '产品',
        'event.type_other': '其他',
        'event.event_date': '时间',
        'event.btn_generate': '生成信号',
        'event.signal_list': '事件信号列表',
        'event.timing_decision': '⏰ 择时决策',

        // Industry Chain
        'industry.title': '产业链图谱',
        'industry.semiconductor': '半导体',
        'industry.new_energy': '新能源',
        'industry.automotive': '汽车',
        'industry.consumption': '消费',
        'industry.btn_load': '加载图谱',
        'industry.propagation': '事件传播路径',
        'industry.event_id_placeholder': '输入事件 ID',
        'industry.btn_propagation': '查看传播路径',

        // Review
        'review.title': '审核队列',
        'review.pending': '待审核断言',
        'review.btn_refresh': '刷新',

        // Signals
        'signals.title': '信号管理',
        'signals.create': '创建新信号',
        'signals.subject_id': '主体 ID',
        'signals.subject_id_placeholder': '如 600000.SH',
        'signals.thesis': '论点',
        'signals.thesis_placeholder': '如 短期看涨',
        'signals.score': '分数 (0~1)',
        'signals.confidence': '置信度 (0~1)',
        'signals.horizon': '预测期',
        'signals.horizon_1d': '1天',
        'signals.horizon_5d': '5天',
        'signals.horizon_20d': '20天',
        'signals.horizon_60d': '60天',
        'signals.btn_create': '创建信号',
        'signals.list': '信号列表',
        'signals.btn_refresh': '刷新',

        // Ingest
        'ingest.title': '文档摄入',
        'ingest.text_label': '文本内容',
        'ingest.text_placeholder': '粘贴研报摘要、新闻内容等...',
        'ingest.source_type': '来源类型',
        'ingest.source_report': '研报',
        'ingest.source_news': '新闻',
        'ingest.source_filing': '公告',
        'ingest.source_other': '其他',
        'ingest.source_name': '来源名称',
        'ingest.source_name_placeholder': '如 中金研报',
        'ingest.doc_title': '标题（可选）',
        'ingest.doc_title_placeholder': '文档标题',
        'ingest.btn_ingest': '摄入',
        'ingest.loading': '正在摄入文档...',

        // Memory
        'memory.title': '记忆与学习',
        'memory.event_type_summary': '事件类型汇总',
        'memory.event_type_placeholder': '输入事件类型，比如 earnings',
        'memory.btn_query': '查询',
        'memory.summary_cards.total_episodes': '总样本数',
        'memory.summary_cards.avg_return': '平均收益',
        'memory.summary_cards.avg_excess': '平均超额收益',
        'memory.summary_cards.win_rate': '胜率',

        'memory.strategy_performance': '策略表现记忆',
        'memory.strategy_id_placeholder': '策略 ID',
        'memory.btn_load_strategy': '加载策略表现',
        'memory.sample_size': '样本数',
        'memory.win_rate': '胜率',
        'memory.avg_return': '平均收益',
        'memory.avg_excess': '平均超额收益',

        'memory.failure_memory': '失败记忆',
        'memory.failure_type_filter': '失败类型筛选',
        'memory.failure_source_filter': '来源 ID 筛选',
        'memory.failure_all': '全部',
        'memory.failure_wrong_thesis': '论点错误',
        'memory.failure_timing_error': '择时错误',
        'memory.failure_crowding_error': '拥挤错误',
        'memory.failure_regime_misread': '环境误判',
        'memory.failure_data_quality': '数据质量',
        'memory.failure_execution_error': '执行错误',
        'memory.failure_risk_error': '风控错误',
        'memory.failure_unknown': '未知',
        'memory.failure_root_cause': '根本原因：',
        'memory.failure_corrective': '修正措施：',
        'memory.failure_source': '来源: ',
        'memory.no_failure': '暂无失败记忆',

        // Review table headers
        'review.table.assertion': '断言',
        'review.table.source': '来源',
        'review.table.status': '状态',
        'review.table.action': '操作',
        'review.btn_approve': '通过',
        'review.btn_reject': '驳回',
        'review.btn_validate': '验证',
        'review.btn_promote': '晋升',

        // Signal table headers
        'signals.table.id': 'ID',
        'signals.table.subject': '主体',
        'signals.table.thesis': '论点',
        'signals.table.score': '分数',
        'signals.table.confidence': '置信度',
        'signals.table.horizon': '预测期',
        'signals.table.status': '状态',
        'signals.table.action': '操作',

        // Toast messages
        'toast.analyze_complete': '资产分析完成',
        'toast.enter_asset_code': '请输入资产代码',
        'toast.scenario_complete': '情景分析完成',
        'toast.enter_topic': '请输入研究主题',
        'toast.ingest_complete': '文档摄入完成',
        'toast.signal_created': '信号创建成功',
        'toast.enter_event_type': '请输入事件类型',

        // Language
        'lang.label': '语言',
        'lang.zh': '中文',
        'lang.en': 'English',

        // Theme
        'theme.light': '亮色',
        'theme.dark': '暗色',
    };

    const en = {
        // Brand / Global
        'brand': 'AlphaFoundry',
        'search.placeholder': 'Search entities, events, signals...',

        // Navigation
        'nav.dashboard': 'Dashboard',
        'nav.explorer': 'Explorer',
        'settings.title': 'Settings',
        'settings.theme': 'Theme',
        'settings.language': 'Language',
        'settings.color_scheme': 'Color',
        'nav.asset-analysis': 'Asset Analysis',
        'nav.scenario': 'Scenario Analysis',
        'nav.event-signal': 'Event Signals',
        'nav.industry-chain': 'Industry Chain',
        'nav.review': 'Review Queue',
        'nav.signals': 'Signal Mgmt',
        'nav.ingest': 'Document Ingest',
        'nav.memory': 'Memory & Learning',

        // Dashboard
        'dashboard.title': 'Dashboard',
        'dashboard.total_signals': 'Total Signals',
        'dashboard.research': 'In Research',
        'dashboard.candidate': 'Candidates',
        'dashboard.paper_trade': 'Paper Trades',
        'dashboard.pending_review': 'Pending Review',
        'dashboard.recent_events': 'Recent Events',
        'dashboard.recent_reports': 'Recent Reports',
        'dashboard.no_data': 'No data',

        // Asset Analysis
        'asset.title': 'Asset Analysis',
        'asset.code_placeholder': 'Enter asset code, e.g. 600000.SH',
        'asset.source_mock': 'Mock Data',
        'asset.source_local': 'Local Data',
        'asset.source_ifind': 'iFinD',
        'asset.btn_analyze': 'Analyze',
        'asset.loading': 'Analyzing asset...',
        'asset.valuation': 'Valuation',
        'asset.fund_flow': 'Fund Flow',
        'asset.price_volume': 'Price & Volume',
        'asset.financial': 'Financials',
        'asset.shareholder': 'Shareholders',
        'asset.industry': 'Industry',
        'asset.event_impact': 'Event Impact',
        'asset.macro': 'Macro',
        'asset.no_data': 'No data',
        'asset.no_financial': 'No financial data',
        'asset.no_fund_flow': 'No fund flow data',
        'asset.no_shareholder': 'No shareholder data',
        'asset.no_industry': 'No industry data',
        'asset.no_event_impact': 'No event impact data',
        'asset.no_macro': 'No macro data',

        // Asset Metrics
        'metric.pe_ttm': 'PE (TTM)',
        'metric.pb': 'PB',
        'metric.ps': 'PS',
        'metric.ev_ebitda': 'EV/EBITDA',
        'metric.revenue': 'Revenue',
        'metric.net_profit': 'Net Profit',
        'metric.eps': 'EPS',
        'metric.roe': 'ROE',
        'metric.main_net_inflow': 'Main Net Inflow',
        'metric.institutional_holding': 'Institutional Holding',
        'metric.northbound_holding': 'Northbound Holding',
        'metric.close_price': 'Close Price',

        // Scenario
        'scenario.title': 'Scenario Analysis',
        'scenario.topic_placeholder': 'Enter research topic, e.g. AI industry development',
        'scenario.subjects_placeholder': 'Related tickers (optional, comma-separated)',
        'scenario.btn_generate': 'Generate Scenarios',
        'scenario.loading': 'Generating scenario analysis...',
        'scenario.prob_chart': 'Scenario Probability Distribution',
        'scenario.residual': 'Residual Uncertainty',
        'scenario.narrative': 'Narrative',
        'scenario.implications': 'Market Implications',
        'scenario.key_drivers': 'Key Drivers',
        'scenario.probability': 'Probability',

        // Event Signal
        'event.title': 'Event Signals',
        'event.trigger': 'Trigger Event Signal',
        'event.event_title': 'Event Title',
        'event.event_title_placeholder': 'Event title',
        'event.event_type': 'Event Type',
        'event.type_earnings': 'Earnings',
        'event.type_policy': 'Policy',
        'event.type_product': 'Product',
        'event.type_other': 'Other',
        'event.event_date': 'Date',
        'event.btn_generate': 'Generate Signal',
        'event.signal_list': 'Event Signal List',
        'event.timing_decision': '⏰ Timing Decision',

        // Industry Chain
        'industry.title': 'Industry Chain Graph',
        'industry.semiconductor': 'Semiconductor',
        'industry.new_energy': 'New Energy',
        'industry.automotive': 'Automotive',
        'industry.consumption': 'Consumption',
        'industry.btn_load': 'Load Graph',
        'industry.propagation': 'Event Propagation Path',
        'industry.event_id_placeholder': 'Enter event ID',
        'industry.btn_propagation': 'View Propagation',

        // Review
        'review.title': 'Review Queue',
        'review.pending': 'Pending Assertions',
        'review.btn_refresh': 'Refresh',

        // Signals
        'signals.title': 'Signal Management',
        'signals.create': 'Create New Signal',
        'signals.subject_id': 'Subject ID',
        'signals.subject_id_placeholder': 'e.g. 600000.SH',
        'signals.thesis': 'Thesis',
        'signals.thesis_placeholder': 'e.g. Short-term bullish',
        'signals.score': 'Score (0~1)',
        'signals.confidence': 'Confidence (0~1)',
        'signals.horizon': 'Horizon',
        'signals.horizon_1d': '1 Day',
        'signals.horizon_5d': '5 Days',
        'signals.horizon_20d': '20 Days',
        'signals.horizon_60d': '60 Days',
        'signals.btn_create': 'Create Signal',
        'signals.list': 'Signal List',
        'signals.btn_refresh': 'Refresh',

        // Ingest
        'ingest.title': 'Document Ingest',
        'ingest.text_label': 'Text Content',
        'ingest.text_placeholder': 'Paste research report excerpt, news content, etc...',
        'ingest.source_type': 'Source Type',
        'ingest.source_report': 'Research Report',
        'ingest.source_news': 'News',
        'ingest.source_filing': 'Filing',
        'ingest.source_other': 'Other',
        'ingest.source_name': 'Source Name',
        'ingest.source_name_placeholder': 'e.g. CICC Research',
        'ingest.doc_title': 'Title (optional)',
        'ingest.doc_title_placeholder': 'Document title',
        'ingest.btn_ingest': 'Ingest',
        'ingest.loading': 'Ingesting document...',

        // Memory
        'memory.title': 'Memory & Learning',
        'memory.event_type_summary': 'Event Type Summary',
        'memory.event_type_placeholder': 'Enter event type, e.g. earnings',
        'memory.btn_query': 'Query',
        'memory.summary_cards.total_episodes': 'Total Episodes',
        'memory.summary_cards.avg_return': 'Avg Return',
        'memory.summary_cards.avg_excess': 'Avg Excess Return',
        'memory.summary_cards.win_rate': 'Win Rate',

        'memory.strategy_performance': 'Strategy Performance Memory',
        'memory.strategy_id_placeholder': 'Strategy ID',
        'memory.btn_load_strategy': 'Load Strategy',
        'memory.sample_size': 'Sample Size',
        'memory.win_rate': 'Win Rate',
        'memory.avg_return': 'Avg Return',
        'memory.avg_excess': 'Avg Excess',

        'memory.failure_memory': 'Failure Memory',
        'memory.failure_type_filter': 'Failure Type Filter',
        'memory.failure_source_filter': 'Source ID Filter',
        'memory.failure_all': 'All',
        'memory.failure_wrong_thesis': 'Wrong Thesis',
        'memory.failure_timing_error': 'Timing Error',
        'memory.failure_crowding_error': 'Crowding Error',
        'memory.failure_regime_misread': 'Regime Misread',
        'memory.failure_data_quality': 'Data Quality',
        'memory.failure_execution_error': 'Execution Error',
        'memory.failure_risk_error': 'Risk Error',
        'memory.failure_unknown': 'Unknown',
        'memory.failure_root_cause': 'Root Cause: ',
        'memory.failure_corrective': 'Corrective Action: ',
        'memory.failure_source': 'Source: ',
        'memory.no_failure': 'No failure memory',

        // Review table headers
        'review.table.assertion': 'Assertion',
        'review.table.source': 'Source',
        'review.table.status': 'Status',
        'review.table.action': 'Action',
        'review.btn_approve': 'Approve',
        'review.btn_reject': 'Reject',
        'review.btn_validate': 'Validate',
        'review.btn_promote': 'Promote',

        // Signal table headers
        'signals.table.id': 'ID',
        'signals.table.subject': 'Subject',
        'signals.table.thesis': 'Thesis',
        'signals.table.score': 'Score',
        'signals.table.confidence': 'Confidence',
        'signals.table.horizon': 'Horizon',
        'signals.table.status': 'Status',
        'signals.table.action': 'Action',

        // Toast messages
        'toast.analyze_complete': 'Asset analysis complete',
        'toast.enter_asset_code': 'Please enter an asset code',
        'toast.scenario_complete': 'Scenario analysis complete',
        'toast.enter_topic': 'Please enter a research topic',
        'toast.ingest_complete': 'Document ingested successfully',
        'toast.signal_created': 'Signal created successfully',
        'toast.enter_event_type': 'Please enter an event type',

        // Language
        'lang.label': 'Language',
        'lang.zh': '中文',
        'lang.en': 'English',

        // Theme
        'theme.light': 'Light',
        'theme.dark': 'Dark',
    };

    // ─── Available Languages ─────────────────────────────────
    const LANGS = { zh, en };

    let currentLang = localStorage.getItem('af-lang') || 'zh';

    // ─── Core API ────────────────────────────────────────────

    /**
     * Get translated text for a key.
     * Falls back to zh if key missing in current lang, then to key itself.
     */
    function t(key) {
        return (LANGS[currentLang] && LANGS[currentLang][key])
            || (LANGS['zh'] && LANGS['zh'][key])
            || key;
    }

    /**
     * Get current language code.
     */
    function getLang() {
        return currentLang;
    }

    /**
     * Switch language and persist choice.
     * Calls optional callback after switch.
     */
    function setLang(lang) {
        if (!LANGS[lang]) {
            console.warn(`[i18n] Unknown language: ${lang}`);
            return;
        }
        currentLang = lang;
        localStorage.setItem('af-lang', lang);
        applyAll();
    }

    /**
     * Apply translations to all elements with [data-i18n] attributes.
     *
     * Usage in HTML:
     *   <span data-i18n="dashboard.title">Dashboard</span>
     *   <input data-i18n-placeholder="search.placeholder">
     *   <button data-i18n-title="review.btn_refresh">Refresh</button>
     */
    function applyAll() {
        // data-i18n → textContent
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            el.textContent = t(key);
        });

        // data-i18n-placeholder → placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            el.setAttribute('placeholder', t(key));
        });

        // data-i18n-title → title
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            el.setAttribute('title', t(key));
        });
    }

    return { t, getLang, setLang, applyAll };
})();
