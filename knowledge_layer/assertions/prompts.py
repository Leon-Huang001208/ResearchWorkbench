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


class AssertionExtractionResult:
    """断言提取结果（用于结构化输出）"""

    subject: str
    predicate: str
    object: str | None = None
    value: float | int | None = None
    observed_at: str | None = None
    confidence: float
