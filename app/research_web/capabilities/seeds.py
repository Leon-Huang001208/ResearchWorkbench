"""Four existing reviewed Skills and two explicitly non-executed workflow templates."""

from pathlib import Path

from .packages import encode_file


def seed_packages():
    root = Path(__file__).parents[1] / "skills"
    specs = [
        ("document-reading", "资料解读", "资料研究"),
        ("company-research", "公司研究", "公司"),
        ("industry-research", "行业研究", "行业"),
        ("fund-evaluation", "基金评价", "基金"),
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
                        "required_tools": ["af_run_script"],
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
                        "required_tools": ["af_run_script"],
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
                                ["af_public_data"]
                                if linked == "fund-evaluation"
                                else ["web_search"]
                            ),
                        },
                        {
                            "title": "来源核对",
                            "instruction": "区分来源、日期与缺失；资料不足不补造。",
                            "skill_id": "document-reading",
                            "tools": ["af_run_script"],
                        },
                        {
                            "title": "分析与交付",
                            "instruction": "调用关联 Skill，实际生成所需文件并核验；显式输出格式优先。",
                            "skill_id": linked,
                            "tools": ["af_run_script"],
                        },
                    ],
                },
            )
        )
    return packages
