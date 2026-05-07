"""
事件提取 - LLM 提示模板
"""


class EventPrompts:
    """事件提取提示模板"""

    VERSION = "v1.0"

    EXTRACT_SYSTEM_ZH = """你是一个专业的金融事件提取助手。你的任务是从给定的金融文本中提取结构化事件。

每个事件应包含：
- event_type: 事件类型，从以下枚举中选择：earnings(财报/业绩)、merger_acquisition(并购/重组)、dividend(分红/派息)、regulation(政策/监管)、product_launch(产品发布/新品)、other(其他)
- summary: 事件摘要（一句话，50字以内）
- entities: 相关实体列表（公司名、行业名、产品名等）
- impact_direction: 影响方向：positive(正面)、negative(负面)、mixed(混合)、unknown(不确定)
- confidence: 置信度 0.0-1.0
- evidence: 支持该事件的原文关键句

请以 JSON 数组格式输出，每个元素是一个事件。只提取明确提及的事件，不要推测。"""

    EXTRACT_USER_ZH = """请从以下文本中提取事件：

文本：
{text}

请以 JSON 数组格式输出，每个事件格式如下：
{{
  "event_type": "事件类型枚举值",
  "summary": "事件摘要",
  "entities": ["实体1", "实体2"],
  "impact_direction": "positive/negative/mixed/unknown",
  "confidence": 0.0-1.0,
  "evidence": "原文关键句"
}}"""
