"""
数字检查器 - 报告编译器第三阶段 3.2.

对编译后章节中的数字做精确验证：
- fabricated number: 正文数字无法匹配任何 fact（虚构成分）
- unit mismatch: 正文数字值与 fact 匹配，但单位不一致
- period mismatch: 正文数字值与 fact 匹配，但期间不一致

全结构化规则驱动，不调用 LLM。输出 list[CritiqueIssue]。
"""

import re

from core.contracts import (
    CompiledSection,
    CritiqueCategory,
    CritiqueIssue,
    FactRecord,
)
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)

_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_CITATION_MARKER_PATTERN = re.compile(r"\[[^\]]*?\d+[^\]]*?\]")

# 数值容差（用于匹配 fact）
_VALUE_TOLERANCE = 0.05

# 常见中文金融单位
_KNOWN_UNITS = [
    "亿元",
    "万元",
    "元",
    "美元",
    "港元",
    "欧元",
    "日元",
    "%",
    "倍",
    "亿",
    "万",
    "吨",
    "家",
    "个",
    "人",
    "Gbps",
    "Mbps",
    "kbps",
    "kW",
    "MW",
    "GW",
    "kWh",
    "bps",
    "pp",
    "百分点",
]

# 期间匹配模式
_PERIOD_PATTERNS = [
    # 绝对期间
    re.compile(r"(\d{4})\s*年"),
    re.compile(r"(\d{4})\s*年\s*第?\s*([一二三1-4])\s*季度"),
    re.compile(r"(\d{4})\s*[Qq]([1-4])"),
    re.compile(r"(\d{4})\s*[Hh]([12])"),
    re.compile(r"[Ff][Yy]\s*(\d{4})"),
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),
    # 相对期间
    re.compile(r"(同比|环比)"),
    re.compile(r"(去年同期|上季度|上半年|下半年|前三季度|全年)"),
    re.compile(r"(年初至今|本季|本年以来)"),
]


class NumericChecker:
    """数字检查器.

    逐一提取正文数字，与事实表中的数值型 fact 进行精确匹配，
    检测虚构数字、单位不一致、期间不一致。
    """

    VALUE_TOLERANCE = _VALUE_TOLERANCE

    def check(
        self,
        sections: list[CompiledSection],
        facts: list[FactRecord],
    ) -> list[CritiqueIssue]:
        """检查所有章节的数字准确性.

        Args:
            sections: 编译后的章节
            facts: 全局事实表

        Returns:
            list[CritiqueIssue]: 数字相关的问题列表
        """
        # 预处理：仅保留有值的 fact
        valued_facts = [f for f in facts if f.value is not None and f.value != 0]

        all_issues: list[CritiqueIssue] = []
        total_numbers = 0
        total_matched = 0

        for section in sections:
            # 提取正文中的所有数字 + 位置 + 上下文
            extracted = self._extract_numbers_from_content(section.content)

            for num_info in extracted:
                total_numbers += 1
                value = num_info["value"]
                unit_text = num_info.get("unit", "")
                period_text = num_info.get("period", "")
                location = num_info.get("location", "")
                num_str = num_info.get("num_str", str(value))

                # 找最接近的事实值
                closest_fact = self._find_closest_fact(value, valued_facts)

                if closest_fact is None:
                    # 虚构数字
                    all_issues.append(
                        CritiqueIssue(
                            issue_id=generate_id(),
                            category=CritiqueCategory.FABRICATED_NUMBER,
                            severity="error",
                            section_id=section.section_id,
                            description=(
                                f"正文数字「{num_str}」{unit_text + ' ' if unit_text else ''}"
                                f"无对应事实支撑"
                            ),
                            location=location,
                            suggested_fix="确认该数字是否可追溯至事实表，否则删除",
                        )
                    )
                    continue

                # 数值匹配成功
                total_matched += 1

                # 检查单位一致性
                if unit_text and closest_fact.unit:
                    if not self._units_match(unit_text, closest_fact.unit):
                        all_issues.append(
                            CritiqueIssue(
                                issue_id=generate_id(),
                                category=CritiqueCategory.UNIT_MISMATCH,
                                severity="warning",
                                section_id=section.section_id,
                                description=(
                                    f"单位不一致：正文使用「{unit_text}」，"
                                    f"事实记录为「{closest_fact.unit}」"
                                    f"（值 {closest_fact.value}）"
                                ),
                                location=location,
                                conflicting_fact_id=closest_fact.fact_id,
                                suggested_fix=f"将正文单位从「{unit_text}」改为「{closest_fact.unit}」",
                            )
                        )

                # 检查期间一致性
                if period_text and closest_fact.period and closest_fact.period != "":
                    if not self._periods_match(period_text, closest_fact.period):
                        all_issues.append(
                            CritiqueIssue(
                                issue_id=generate_id(),
                                category=CritiqueCategory.PERIOD_MISMATCH,
                                severity="info",
                                section_id=section.section_id,
                                description=(
                                    f"期间不一致：正文引用「{period_text}」，"
                                    f"事实记录为「{closest_fact.period}」"
                                    f"（值 {closest_fact.value}）"
                                ),
                                location=location,
                                conflicting_fact_id=closest_fact.fact_id,
                                suggested_fix=(
                                    f"将正文期间从「{period_text}」改为「{closest_fact.period}」"
                                ),
                            )
                        )

        logger.info(
            "Numeric check complete",
            sections=len(sections),
            total_numbers=total_numbers,
            matched=total_matched,
            issues=len(all_issues),
        )
        return all_issues

    # ── 数字提取 ───────────────────────────────────────────────────────

    def _extract_numbers_from_content(self, content: str) -> list[dict]:
        """从正文提取所有数字及其上下文.

        返回 list[dict]，每个 dict 含:
            value: float, num_str: str, unit: str, period: str,
            location: str (150 chars 上下文), position: int
        """
        results: list[dict] = []
        if not content:
            return results

        # 剔除引用标记
        clean_content = _CITATION_MARKER_PATTERN.sub("", content)

        for m in _NUMBER_PATTERN.finditer(clean_content):
            val = float(m.group())
            n_str = m.group()

            # 过滤年份（4 位且在合理范围内）
            if len(n_str) == 4 and 1990 <= int(val) <= 2099:
                continue
            # 过滤纯序号标记（如第1/第2）
            start = m.start()
            if start >= 1 and clean_content[start - 1] == "第":
                continue

            pos = m.start()
            # 提取附近的单位
            unit_text = self._extract_unit_near_number(clean_content, pos, n_str)
            # 提取附近的期间
            period_text = self._extract_period_near_number(clean_content, pos)
            # 提取上下文（前后 75 char）
            ctx_start = max(0, pos - 75)
            ctx_end = min(len(clean_content), pos + len(n_str) + 75)
            location = clean_content[ctx_start:ctx_end]

            results.append(
                {
                    "value": val,
                    "num_str": n_str,
                    "unit": unit_text,
                    "period": period_text,
                    "location": location,
                    "position": pos,
                }
            )

        return results

    def _extract_unit_near_number(self, text: str, pos: int, num_str: str) -> str:
        """提取数字附近的单位文本.

        在数字后 ±10 字符窗口内查找已知单位。优先匹配更长单位（亿元 > 元），
        优先匹配后区间（紧邻数字之后），前区间仅作备选。
        """
        # 按长度降序排列，避免短单位子串匹配（如 "元" 错误匹配 "亿元" 中的 "元"）
        units_sorted = sorted(_KNOWN_UNITS, key=len, reverse=True)

        # 数字后 10 字符窗口（优先）
        after_start = pos + len(num_str)
        after_end = min(len(text), after_start + 10)
        after_text = text[after_start:after_end]

        for unit in units_sorted:
            if unit in after_text[: len(unit) + 2]:  # 单位应在紧邻位置
                return unit

        # 数字前 5 字符窗口（备选，如 "$100"）
        before_start = max(0, pos - 5)
        before_text = text[before_start:pos]

        for unit in units_sorted:
            if unit in before_text:
                return unit

        return ""

    def _extract_period_near_number(self, text: str, pos: int) -> str:
        """提取数字附近的期间文本.

        在数字 ±30 字符窗口内查找期间模式，返回距离数字最近的匹配。
        """
        window_start = max(0, pos - 30)
        window_end = min(len(text), pos + 30)
        window = text[window_start:window_end]

        best_match = ""
        best_dist = float("inf")

        for pattern in _PERIOD_PATTERNS:
            for match in pattern.finditer(window):
                match_mid = (match.start() + match.end()) // 2
                # 数字在窗口中的位置
                num_pos_in_window = pos - window_start
                dist = abs(match_mid - num_pos_in_window)
                if dist < best_dist:
                    best_dist = dist
                    best_match = match.group(0)

        return best_match

    # ── Fact 匹配 ──────────────────────────────────────────────────────

    def _find_closest_fact(self, value: float, valued_facts: list[FactRecord]) -> FactRecord | None:
        """在数值型 fact 中找最接近的匹配（容差 ±5%）."""
        best: tuple[float, FactRecord | None] = (float("inf"), None)
        for fact in valued_facts:
            if fact.value is None or fact.value == 0:
                continue
            rel_err = abs(value - fact.value) / abs(fact.value)
            if rel_err < self.VALUE_TOLERANCE and rel_err < best[0]:
                best = (rel_err, fact)

        return best[1]

    # ── 一致性检查 ────────────────────────────────────────────────────

    @staticmethod
    def _units_match(text_unit: str, fact_unit: str) -> bool:
        """检查正文单位与事实单位是否一致.

        处理常见同义词和写法差异。
        """
        a = text_unit.strip().lower()
        b = fact_unit.strip().lower()

        if a == b:
            return True

        # 同义词归一化
        synonyms = [
            ({"%", "pct", "percent", "百分比"}, {"%", "pct", "percent", "百分比"}),
            ({"亿元", "亿"}, {"亿元", "亿"}),
            ({"万元", "万"}, {"万元", "万"}),
            ({"元", "rmb", "cny"}, {"元", "rmb", "cny"}),
            ({"美元", "usd", "$"}, {"美元", "usd", "$"}),
            ({"倍", "x", "倍数"}, {"倍", "x", "倍数"}),
            ({"bps", "bp"}, {"bps", "bp"}),
        ]

        for group_a, group_b in synonyms:
            if a in group_a and b in group_b:
                return True

        return False

    @staticmethod
    def _periods_match(text_period: str, fact_period: str) -> bool:
        """检查正文期间与事实期间是否一致.

        处理相对期间（同比/环比）和绝对期间（2024Q1 等同义词）。
        """
        tp = text_period.strip()
        fp = fact_period.strip()

        if not tp or not fp:
            return True  # 只要有一个缺失则不比较

        if tp == fp:
            return True

        # 相对期间不做精确定匹配（总是算作 match，避免误报）
        relative_indicators = {"同比", "环比", "去年同期", "上季度", "年初至今", "本季"}
        if any(ind in tp for ind in relative_indicators):
            return True

        # 提取年份
        tp_year = _extract_year(tp)
        fp_year = _extract_year(fp)
        if tp_year is not None and fp_year is not None and tp_year != fp_year:
            return False

        # 提取季度
        tp_q = _extract_quarter(tp)
        fp_q = _extract_quarter(fp)
        if tp_q is not None and fp_q is not None and tp_q != fp_q:
            return False

        # 提取半年度
        tp_h = _extract_half(tp)
        fp_h = _extract_half(fp)
        if tp_h is not None and fp_h is not None and tp_h != fp_h:
            return False

        return True


def _extract_year(text: str) -> int | None:
    """从文本中提取年份."""
    m = re.search(r"(\d{4})\s*年?", text)
    if m:
        return int(m.group(1))
    m = re.search(r"[Ff][Yy]\s*(\d{4})", text)
    if m:
        return int(m.group(1))
    return None


def _extract_quarter(text: str) -> int | None:
    """从文本中提取季度."""
    # Q1, Q2, ...
    m = re.search(r"[Qq]([1-4])", text)
    if m:
        return int(m.group(1))
    # 第n季度
    m = re.search(r"第\s*([一二三四1-4])\s*季度", text)
    if m:
        q_map = {"一": 1, "二": 2, "三": 3, "四": 4, "1": 1, "2": 2, "3": 3, "4": 4}
        return q_map.get(m.group(1))
    return None


def _extract_half(text: str) -> int | None:
    """从文本中提取半年度."""
    m = re.search(r"[Hh]([12])", text)
    if m:
        return int(m.group(1))
    return None
