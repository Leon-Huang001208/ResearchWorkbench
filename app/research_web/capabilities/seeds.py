"""Reviewed built-in Skills and explicitly non-executed workflow templates."""

from pathlib import Path

from .packages import encode_file


def seed_packages():
    root = Path(__file__).parents[1] / "skills"
    specs = [
        ("document-reading", "资料解读", "资料研究"),
        ("company-research", "公司研究", "公司"),
        ("industry-research", "行业研究", "行业"),
        ("fund-evaluation", "基金评价", "基金"),
        ("market-commentary", "市场解读", "市场"),
        ("factor-database-research", "因子库研究", "因子研究"),
    ]
    packages = []
    for slug, name, category in specs:
        folder = root / slug
        files = [
            encode_file(p.relative_to(folder).as_posix(), p.read_bytes())
            for p in sorted(folder.rglob("*"))
            if p.is_file() and p.name != "SKILL.md" and "__pycache__" not in p.parts
        ]
        packages.append(
            (
                slug,
                {
                    "kind": "skill",
                    "metadata": {
                        "slug": slug,
                        "name": name,
                        "description": f"基于实际材料开展{name}，保留来源、口径及数据缺失，按需交付真实文件。",
                        "category": category,
                        "inputs": [
                            {
                                "name": "question",
                                "label": "研究问题与资料",
                                "type": "text",
                                "required": True,
                            }
                        ],
                        "scenarios": [name],
                        "default_formats": (
                            [] if slug == "document-reading" else ["docx", "html", "xlsx"]
                        ),
                        "required_tools": [
                            "research_run_script",
                            *(
                                ["datahub_get_database_schema", "datahub_query_table"]
                                if slug == "factor-database-research"
                                else (
                                    ["datahub_get_fund_data"]
                                    if slug == "fund-evaluation"
                                    else ["datahub_search_news"]
                                )
                            ),
                        ],
                        "dependencies": [],
                    },
                    "instructions": (folder / "SKILL.md").read_text(),
                    "files": files,
                    "steps": [],
                    "reviewed_scripts": [f["sha256"] for f in files if f["path"].endswith(".py")],
                },
            )
        )
    for slug, name, linked, preparation in [
        (
            "market-commentary-workflow",
            "市场资料筛选与解读交付",
            "market-commentary",
            "由父 Agent 经原生审批取得市场资讯快照，核对日期、覆盖和来源后再进行筛选。",
        ),
        (
            "fund-research-workflow",
            "基金资料准备与受限评价",
            "fund-evaluation",
            "由父 Agent 经原生审批准备可用净值、基本资料、分红和持仓，核对 manifest。",
        ),
        (
            "company-research-workflow",
            "公司资料研究与报告交付",
            "company-research",
            "确认公司身份、期间与用户上传资料；仅通过现有工具补充有来源的材料。",
        ),
        (
            "report-production-workflow",
            "报告项目资料准备与文件交付",
            "company-research",
            "核对报告项目锁定版本、模板、底稿、数据配方和必需输出；先准备一份共享资料包。",
        ),
    ]:
        packages.append(
            (
                slug,
                {
                    "kind": "workflow",
                    "metadata": {
                        "slug": slug,
                        "name": name,
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
                        "scenarios": [name],
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
                            "instruction": preparation,
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
        )
    return packages
