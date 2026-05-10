"""
断言提取 - LLM 提示模板
"""


class AssertionPrompts:
    """断言提取提示模板"""

    VERSION = "v1.0"

    EXTRACT_SYSTEM = """你是一个专业的金融事实提取助手。你的任务是从给定的文本中提取结构化的事实断言。

每个断言应包含：
- subject: 主体（公司、资产、机构等）
- predicate: 谓语（增长、下降、发布、收购等）
- object: 宾语（数值、产品、公司等）
- value: 数值（如果有）
- observed_at: 观察时间（如果有）

请以 JSON 数组格式输出，每个元素是一个断言。
"""

    EXTRACT_USER = """请从以下文本中提取事实断言：

文本：
{text}

请以 JSON 数组格式输出，每个断言格式如下：
{{
  "subject": "主体",
  "predicate": "谓语",
  "object": "宾语",
  "value": 数值或null,
  "observed_at": "日期字符串或null",
  "confidence": 0.0-1.0
}}
"""

    # 中文版本
    EXTRACT_SYSTEM_ZH = """你是一个专业的金融事实提取助手。你的任务是从给定的文本中提取结构化的事实断言。

每个断言应包含：
- subject: 主体（公司、资产、机构等）
- predicate: 谓语（增长、下降、发布、收购等）
- object: 宾语（数值、产品、公司等）
- value: 数值（如果有）
- observed_at: 观察时间（如果有）

请以 JSON 数组格式输出，每个元素是一个断言。
"""

    EXTRACT_USER_ZH = """请从以下文本中提取事实断言：

文本：
{text}

请以 JSON 数组格式输出，每个断言格式如下：
{{
  "subject": "主体",
  "predicate": "谓语",
  "object": "宾语",
  "value": 数值或null,
  "observed_at": "日期字符串或null",
  "confidence": 0.0-1.0
}}
"""

    # 合并提取 prompt（断言+事件一次 LLM 调用）
    COMBINED_EXTRACT_SYSTEM_ZH = """你是一个专业的金融文本分析助手。你的任务是从给定的金融文本中同时提取结构化的事实断言和事件。

断言格式：
- subject: 主体（公司、资产、机构等）
- predicate: 谓语（增长、下降、发布、收购等）
- object: 宾语（数值、产品、公司等）
- value: 数值（如果有）
- confidence: 置信度 0.0-1.0

事件格式：
- event_type: 事件类型（earnings/merger_acquisition/dividend/regulation/product_launch/other）
- summary: 事件摘要（50字以内）
- entities: 相关实体列表
- impact_direction: 影响方向（positive/negative/mixed/unknown）
- confidence: 置信度 0.0-1.0
- evidence: 原文关键句

输出JSON格式：
{
  "assertions": [...],
  "events": [...]
}"""

    COMBINED_EXTRACT_USER_ZH = """请从以下文本中同时提取断言和事件：

文本：
{text}

输出格式：
{{
  "assertions": [
    {{"subject": "主体", "predicate": "谓语", "object": "宾语", "value": 数值或null, "confidence": 0.0-1.0}}
  ],
  "events": [
    {{"event_type": "类型", "summary": "摘要", "entities": ["实体"], "impact_direction": "方向", "confidence": 0.0-1.0, "evidence": "原文"}}
  ]
}}"""


class AssertionExtractionResult:
    """断言提取结果（用于结构化输出）"""

    subject: str
    predicate: str
    object: str | None = None
    value: float | int | None = None
    observed_at: str | None = None
    confidence: float
