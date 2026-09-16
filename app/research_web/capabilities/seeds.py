"""Reviewed built-in Skills and explicitly non-executed workflow templates."""

from pathlib import Path

from .packages import encode_file

QUESTION_INPUT = {
    "name": "question",
    "label": "研究问题与资料",
    "type": "text",
    "required": True,
}

# Metadata is declared here rather than inferred from directories. This keeps the
# product catalog stable while allowing each Skill to describe a narrow trigger.
SKILL_SPECS = (
    {
        "slug": "document-reading",
        "name": "资料解读",
        "description": "基于实际材料开展资料解读，保留来源、口径及数据缺失，按需交付真实文件。",
        "category": "资料研究",
        "scenarios": ["资料解读"],
        "default_formats": [],
        "required_tools": ["research_run_script", "datahub_search_news"],
        "evidence_protocol": False,
    },
    {
        "slug": "company-research",
        "name": "公司研究",
        "description": "基于实际材料开展公司研究，保留来源、口径及数据缺失，按需交付真实文件。",
        "category": "公司",
        "scenarios": ["公司研究"],
        "default_formats": ["docx", "html", "xlsx"],
        "required_tools": ["research_run_script", "datahub_search_news"],
        "evidence_protocol": False,
    },
    {
        "slug": "industry-research",
        "name": "行业研究",
        "description": "基于实际材料开展行业研究，保留来源、口径及数据缺失，按需交付真实文件。",
        "category": "行业",
        "scenarios": ["行业研究"],
        "default_formats": ["docx", "html", "xlsx"],
        "required_tools": ["research_run_script", "datahub_search_news"],
        "evidence_protocol": False,
    },
    {
        "slug": "fund-evaluation",
        "name": "基金评价",
        "description": "基于实际材料开展基金评价，保留来源、口径及数据缺失，按需交付真实文件。",
        "category": "基金",
        "scenarios": ["基金评价"],
        "default_formats": ["docx", "html", "xlsx"],
        "required_tools": ["research_run_script", "datahub_get_fund_data"],
        "evidence_protocol": False,
    },
    {
        "slug": "market-commentary",
        "name": "市场解读",
        "description": "基于实际材料开展市场解读，保留来源、口径及数据缺失，按需交付真实文件。",
        "category": "市场",
        "scenarios": ["市场解读"],
        "default_formats": ["docx", "html", "xlsx"],
        "required_tools": ["research_run_script", "datahub_search_news"],
        "evidence_protocol": False,
    },
    {
        "slug": "factor-database-research",
        "name": "因子库研究",
        "description": "基于实际材料开展因子库研究，保留来源、口径及数据缺失，按需交付真实文件。",
        "category": "因子研究",
        "scenarios": ["因子库研究"],
        "default_formats": ["docx", "html", "xlsx"],
        "required_tools": [
            "research_run_script",
            "datahub_get_database_schema",
            "datahub_query_table",
        ],
        "evidence_protocol": False,
    },
    {
        "slug": "sell-side-report-reader",
        "name": "研报增量分析",
        "description": "聚焦卖方研报或研究文章的增量、公开时序、可信度与证伪；不用于一般资料提取或个人买卖建议。",
        "category": "研报与资料",
        "scenarios": ["研报增量与公开时序研究"],
        "default_formats": [],
        "required_tools": ["research_run_script", "web_search"],
        "evidence_protocol": True,
    },
    {
        "slug": "finance-news-event-research",
        "name": "金融事件研究",
        "description": "聚焦单一、有时间戳的金融事件，核验事实并分析传导链；不用于多事件市场复盘或盘前综述。",
        "category": "事件与政策",
        "scenarios": ["单一金融事件影响研究"],
        "default_formats": [],
        "required_tools": ["web_search"],
        "evidence_protocol": True,
    },
    {
        "slug": "industry-chain-research",
        "name": "产业链与主题研究",
        "description": "聚焦价值流、瓶颈、阶段和受益/受损映射；不替代覆盖供需、竞争格局与关键指标的通用行业报告。",
        "category": "行业与主题",
        "scenarios": ["产业链与主题传导研究"],
        "default_formats": [],
        "required_tools": ["web_search"],
        "evidence_protocol": True,
    },
    {
        "slug": "earnings-consensus-research",
        "name": "业绩与一致预期",
        "description": "聚焦单家公司业绩、指引、预期差和机构分歧；不替代业务、财务、竞争力、估值与风险俱全的完整公司研究。",
        "category": "公司与业绩",
        "scenarios": ["业绩与一致预期差研究"],
        "default_formats": [],
        "required_tools": ["web_search"],
        "evidence_protocol": True,
    },
    {
        "slug": "macro-asset-research",
        "name": "宏观与跨资产",
        "description": "研究宏观制度、政策、流动性及其跨资产传导；不用于单一公司、产业链或日常多事件复盘。",
        "category": "宏观与资产",
        "scenarios": ["宏观政策与跨资产传导研究"],
        "default_formats": [],
        "required_tools": ["web_search"],
        "evidence_protocol": True,
    },
    {
        "slug": "framework-research",
        "name": "框架深度验证",
        "description": "基于服务器绑定的版本化框架与快照补充证据，保留反证、日期、口径和数据缺口。",
        "category": "研究框架",
        "scenarios": ["框架页面显式深度验证"],
        "default_formats": [],
        "required_tools": [
            "web_search",
            "datahub_get_factor_macro",
            "datahub_search_news",
            "datahub_search_research",
        ],
        "evidence_protocol": True,
    },
    {
        "slug": "daily-market-brief",
        "name": "每日市场简报",
        "description": "将市场快照、涨跌成交、行业主题与新闻证据编排为固定结构简报；不替代事件或政策分析。",
        "category": "市场监控",
        "scenarios": ["每日市场证据简报"],
        "default_formats": [],
        "required_tools": [
            "research_run_script",
            "datahub_get_index_data",
            "datahub_get_market_snapshot",
            "datahub_get_market_activity",
            "datahub_search_news",
        ],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "结构化市场输入", "type": "file", "required": True},
            {"name": "as_of", "label": "数据截止日", "type": "date", "required": True},
        ],
    },
    {
        "slug": "policy-sentinel",
        "name": "政策哨兵",
        "description": "按关键词和日期输出政策证据时间线、命中规则与来源已给出的潜在影响对象；不生成投资建议。",
        "category": "事件与政策",
        "scenarios": ["政策证据监控"],
        "default_formats": [],
        "required_tools": [
            "research_run_script",
            "datahub_search_news",
            "datahub_search_announcements",
        ],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "政策记录", "type": "file", "required": True},
            {"name": "as_of", "label": "数据截止日", "type": "date", "required": True},
        ],
    },
    {
        "slug": "event-review",
        "name": "事件复盘",
        "description": "确定性计算事件窗收益、超额表现、成交变化及可用的 beta/alpha；不使用默认 beta。",
        "category": "事件与政策",
        "scenarios": ["标的事件窗口复盘"],
        "default_formats": [],
        "required_tools": ["research_run_script", "datahub_get_market_bars"],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "标的与基准日频序列", "type": "file", "required": True},
            {"name": "event_date", "label": "事件日期", "type": "date", "required": True},
        ],
    },
    {
        "slug": "etf-flow-monitor",
        "name": "ETF 资金流监控",
        "description": "由 ETF 份额变化和 NAV 估算资金流，严格按用户提供的类型、行业和主题分类汇总。",
        "category": "基金",
        "scenarios": ["ETF 份额资金流监控"],
        "default_formats": [],
        "required_tools": [
            "research_run_script",
            "datahub_get_fund_data",
            "datahub_query_table",
        ],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "ETF 份额与分类输入", "type": "file", "required": True}
        ],
    },
    {
        "slug": "earnings-report-monitor",
        "name": "财报披露监控",
        "description": "按证券、报告期、披露日及营收净利同比环比记录，计算披露进度和变化分布。",
        "category": "公司与业绩",
        "scenarios": ["财报披露进度监控"],
        "default_formats": [],
        "required_tools": [
            "research_run_script",
            "datahub_get_financials",
            "datahub_query_table",
        ],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "财报披露记录", "type": "file", "required": True}
        ],
    },
    {
        "slug": "earnings-preview-monitor",
        "name": "业绩预告监控",
        "description": "计算业绩预告利润和增速区间中值，仅汇总输入已提供的估值、资金与研究覆盖字段。",
        "category": "公司与业绩",
        "scenarios": ["业绩预告区间监控"],
        "default_formats": [],
        "required_tools": [
            "research_run_script",
            "datahub_get_financials",
            "datahub_get_market_snapshot",
            "datahub_get_market_activity",
            "datahub_search_research",
            "datahub_query_table",
        ],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "业绩预告记录", "type": "file", "required": True}
        ],
    },
    {
        "slug": "fund-matcher",
        "name": "基金匹配",
        "description": "按明确类别、目标指标与权重对已提供候选基金做确定性距离排序。",
        "category": "基金",
        "scenarios": ["基金候选匹配"],
        "default_formats": [],
        "required_tools": ["research_run_script", "datahub_get_fund_data"],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "基金指标输入", "type": "file", "required": True}
        ],
    },
    {
        "slug": "fund-penetration",
        "name": "基金持仓穿透",
        "description": "统一权重单位并穿透基金层级，检测循环并聚合重复底层暴露。",
        "category": "基金",
        "scenarios": ["基金持仓穿透"],
        "default_formats": [],
        "required_tools": ["research_run_script", "datahub_get_fund_data"],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "基金层级持仓", "type": "file", "required": True}
        ],
    },
    {
        "slug": "portfolio-overlap",
        "name": "组合重合度",
        "description": "归一化两个组合的持仓权重，计算逐资产共同权重与总体重合度。",
        "category": "组合",
        "scenarios": ["组合持仓重合分析"],
        "default_formats": [],
        "required_tools": ["research_run_script", "datahub_get_fund_data", "datahub_query_table"],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "两个组合持仓", "type": "file", "required": True}
        ],
    },
    {
        "slug": "portfolio-benchmark-deviation",
        "name": "组合基准偏离",
        "description": "计算组合相对基准的行业权重差及市值、估值、增速标准差偏离。",
        "category": "组合",
        "scenarios": ["组合基准偏离监控"],
        "default_formats": [],
        "required_tools": ["research_run_script", "datahub_get_index_data", "datahub_query_table"],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "组合与基准持仓因子", "type": "file", "required": True}
        ],
    },
    {
        "slug": "industry-prosperity",
        "name": "行业景气度",
        "description": "对预聚合行业指标按明确方向和权重计算透明景气变化分数。",
        "category": "行业",
        "scenarios": ["行业景气度研究"],
        "default_formats": [],
        "required_tools": ["research_run_script", "datahub_query_table"],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "行业预聚合指标", "type": "file", "required": True}
        ],
    },
    {
        "slug": "industry-quadrant-monitor",
        "name": "行业象限监控",
        "description": "按显式水平和动量阈值，将预聚合行业景气分数划分四象限。",
        "category": "行业",
        "scenarios": ["行业景气象限监控"],
        "default_formats": [],
        "required_tools": ["research_run_script", "datahub_query_table"],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "行业景气分数", "type": "file", "required": True}
        ],
    },
    {
        "slug": "industry-crowding-monitor",
        "name": "行业拥挤度",
        "description": "用预聚合行业与全市场成交额计算滚动成交占比和历史经验分位数。",
        "category": "行业",
        "scenarios": ["行业成交拥挤度监控"],
        "default_formats": [],
        "required_tools": ["research_run_script", "datahub_query_table"],
        "evidence_protocol": False,
        "cpu_profile": True,
        "inputs": [
            {"name": "input_file", "label": "行业预聚合成交额", "type": "file", "required": True}
        ],
    },
)

RECEIPT_GATED_SKILLS = frozenset(
    {
        "daily-market-brief",
        "policy-sentinel",
        "event-review",
        "etf-flow-monitor",
        "earnings-report-monitor",
        "earnings-preview-monitor",
        "fund-matcher",
        "fund-penetration",
        "portfolio-overlap",
        "portfolio-benchmark-deviation",
        "industry-prosperity",
        "industry-quadrant-monitor",
        "industry-crowding-monitor",
    }
)

# Exact scripts shipped by the first Stage 2 seed commit. Only these known
# immutable built-ins are eligible for the one-way safety migration.
LEGACY_STAGE2_SCRIPT_SHA256 = {
    "daily-market-brief": "d63e3750cfb28c2be5e3c492e2ba5bed73fe6914e8fa41033e19613fe330b05e",
    "policy-sentinel": "a78ae122087231c72b95d98749c1e6a0e764b89336d8c413538025b6faac75d9",
    "event-review": "6519b155074b9cc57af7bd6410e7379793d338b51bef67cc23682416415b9a8d",
    "etf-flow-monitor": "3b9d77321f185a570c8d481ec86021c65ac813ad393f6ee293645b2cdeb776c9",
    "earnings-report-monitor": "fa5c5f36119380028cb4bcb170cb80b84c7c0aaf8f9296939e25410a287d2c59",
    "earnings-preview-monitor": "189e96f9fcde39a388cf765196eea6e38d9fb25a224fe8a8fcb98668b5a304f1",
}

# Exact scripts shipped by the first Stage 3 seed commit. Matching by the
# immutable file digest prevents user or later built-in versions from being
# rewritten by this one-way safety migration.
LEGACY_STAGE3_SCRIPT_SHA256 = {
    "fund-matcher": "e0d0b61aeae71ffd409f0cdddd42d459c874b06dfcb489524b1e49e2692b978f",
    "fund-penetration": "ae4349dfbc3755b599eec265d70bce4e5470791c312c211f6f747900df11dc54",
    "portfolio-overlap": "454419b2b58a720c364d3bf3883be3840adb35fdd38152f1204b0fe3e2c1df5f",
    "portfolio-benchmark-deviation": "c216c3ea377ae6fa5ace72260ce60b909fdefa7fe813200f7988112801f2b80a",
    "industry-prosperity": "31df916c150ea791f7581a817e1efc19f33f6581b4ca8967feff0a5ed1225da2",
    "industry-quadrant-monitor": "c3efd22876b06bacc39ba56cba411de1075fe5b0b884c15855be59a5d9175513",
    "industry-crowding-monitor": "418a7eb9003c3242202d772d5493ce6a7b36813db5c882f7c522953bdfaf33db",
}


def builtin_initial_status(capability_id: str) -> str:
    """Keep uncalibrated calculators discoverable but non-executable."""
    return "disabled" if capability_id in RECEIPT_GATED_SKILLS else "enabled"


WORKFLOW_SPECS = (
    {
        "slug": "market-commentary-workflow",
        "name": "市场资料筛选与解读交付",
        "linked": "market-commentary",
        "preparation": "由父 Agent 经原生审批取得市场资讯快照，核对日期、覆盖和来源后再进行筛选。",
    },
    {
        "slug": "fund-research-workflow",
        "name": "基金资料准备与受限评价",
        "linked": "fund-evaluation",
        "preparation": "由父 Agent 经原生审批准备可用净值、基本资料、分红和持仓，核对 manifest。",
    },
    {
        "slug": "company-research-workflow",
        "name": "公司资料研究与报告交付",
        "linked": "company-research",
        "preparation": "确认公司身份、期间与用户上传资料；仅通过现有工具补充有来源的材料。",
    },
    {
        "slug": "report-production-workflow",
        "name": "报告项目资料准备与文件交付",
        "linked": "company-research",
        "preparation": "核对报告项目锁定版本、模板、底稿、数据配方和必需输出；先准备一份共享资料包。",
    },
)


def _skill_package(root, spec, protocol):
    folder = root / spec["slug"]
    files = [
        encode_file(path.relative_to(folder).as_posix(), path.read_bytes())
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.name != "SKILL.md" and "__pycache__" not in path.parts
    ]
    if spec["evidence_protocol"]:
        files.append(encode_file("references/evidence-protocol.md", protocol.read_bytes()))
    if spec.get("cpu_profile"):
        shared = root / "_shared"
        for source_name, package_name in (
            ("cpu-bounded-policy.md", "references/cpu-bounded-policy.md"),
            ("cpu-bounded-result-v1.md", "references/cpu-bounded-result-v1.md"),
            ("provenance-v1.md", "references/provenance-v1.md"),
            ("cpu_budget.py", "scripts/cpu_budget.py"),
            ("input_contract.py", "scripts/input_contract.py"),
        ):
            files.append(encode_file(package_name, (shared / source_name).read_bytes()))
    metadata = {
        "slug": spec["slug"],
        "name": spec["name"],
        "description": spec["description"],
        "category": spec["category"],
        "inputs": [dict(item) for item in spec.get("inputs", [QUESTION_INPUT])],
        "scenarios": list(spec["scenarios"]),
        "default_formats": list(spec["default_formats"]),
        "required_tools": list(spec["required_tools"]),
        "dependencies": [],
    }
    return (
        spec["slug"],
        {
            "kind": "skill",
            "metadata": metadata,
            "instructions": (folder / "SKILL.md").read_text(encoding="utf-8"),
            "files": files,
            "steps": [],
            "reviewed_scripts": [item["sha256"] for item in files if item["path"].endswith(".py")],
        },
    )


def _workflow_package(spec):
    linked = spec["linked"]
    return (
        spec["slug"],
        {
            "kind": "workflow",
            "metadata": {
                "slug": spec["slug"],
                "name": spec["name"],
                "description": "有序研究步骤模板；并不表示任何步骤已经执行。",
                "category": "研究流程",
                "inputs": [
                    {
                        "name": "question",
                        "label": "对象、期间与资料",
                        "type": "text",
                        "required": True,
                    }
                ],
                "scenarios": [spec["name"]],
                "default_formats": ["docx", "html", "xlsx"],
                "required_tools": ["research_run_script"],
                "dependencies": [],
            },
            "instructions": "",
            "files": [],
            "reviewed_scripts": [],
            "steps": [
                {
                    "title": "资料准备",
                    "instruction": spec["preparation"],
                    "tools": (
                        ["datahub_get_fund_data"]
                        if linked == "fund-evaluation"
                        else (
                            ["datahub_search_news"]
                            if linked == "market-commentary"
                            else ["web_search"]
                        )
                    ),
                },
                {
                    "title": "来源核对",
                    "instruction": "区分来源、日期与缺失；资料不足不补造。",
                    "skill_id": "document-reading",
                    "tools": ["research_run_script"],
                },
                {
                    "title": "分析与交付",
                    "instruction": "调用关联 Skill，实际生成所需文件并核验；显式输出格式优先。",
                    "skill_id": linked,
                    "tools": ["research_run_script"],
                },
            ],
        },
    )


def seed_packages():
    root = Path(__file__).parents[1] / "skills"
    protocol = root / "_shared" / "evidence-protocol.md"
    return [
        *(_skill_package(root, spec, protocol) for spec in SKILL_SPECS),
        *(_workflow_package(spec) for spec in WORKFLOW_SPECS),
    ]
