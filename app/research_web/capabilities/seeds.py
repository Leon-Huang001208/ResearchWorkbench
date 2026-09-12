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
)

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
    metadata = {
        "slug": spec["slug"],
        "name": spec["name"],
        "description": spec["description"],
        "category": spec["category"],
        "inputs": [dict(QUESTION_INPUT)],
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
