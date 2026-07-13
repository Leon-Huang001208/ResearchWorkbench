from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SECTION_CONFIG = ROOT / "report_projects" / "华安ETF周报" / "config" / "section_config.yaml"
PROMPT_TEMPLATES = ROOT / "report_projects" / "华安ETF周报" / "config" / "prompt_templates.md"


def test_oil_prompt_is_causal_and_does_not_pollute_shared_constraints():
    config = yaml.safe_load(SECTION_CONFIG.read_text(encoding="utf-8"))
    prompt_source = PROMPT_TEMPLATES.read_text(encoding="utf-8")
    common_constraints = "\n".join(config["defaults"]["generation_constraints"])
    oil = config["placeholders"]["原油"]
    oil_structure = "\n".join(oil["writing_structure"])
    oil_prompt = prompt_source.split("## 原油\n", 1)[1].split("\n## ", 1)[0]

    for oil_only_term in ["OPEC+", "原油库存", "霍尔木兹", "布伦特", "WTI"]:
        assert oil_only_term not in common_constraints

    assert "交易主线" in oil_structure
    assert "支撑因素" in oil_structure
    assert "压制因素" in oil_structure
    assert "不强行覆盖" in oil_structure
    assert "3—5" in oil_structure
    assert "具体事实、数字和事件必须来自 Evidence" in oil_structure
    assert "不得输出来源括号" in oil_structure
    assert "直接解释本周国际油价变动" in oil_prompt

    retrieval = oil["retrieval"]
    assert "top_k" not in retrieval
    assert config["defaults"]["retrieval"]["top_k"] == 10
    assert "EIA原油库存" in retrieval["keywords"]
    assert "OPEC+" in retrieval["keywords"]
    assert "2040年" in retrieval["exclude"]
    assert "航空煤油" in retrieval["exclude"]
