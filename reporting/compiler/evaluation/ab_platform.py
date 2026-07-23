"""
A/B 对比平台 - 报告编译器第三阶段 3.3.

对两份 EvaluationReport 做逐维度对比，产出 ABComparison。
所有对比纯规则驱动，不调用 LLM。
盲评模式随机交换标签，仅在对比完成后揭示真实身份。
"""

import hashlib
import random
import time

from core.contracts import ABComparison, ABDimensionDiff, EvaluationReport
from core.observability import get_logger

logger = get_logger(__name__)

# 可对比的 ReportMetrics 维度列表
_COMPARABLE_DIMENSIONS: list[tuple[str, str, bool]] = [
    # (dimension key, display name, higher_is_better)
    ("source_tier_a_b_ratio", "检索质量-官方源占比", True),
    ("evidence_diversity", "检索质量-来源多样性", True),
    ("claim_support_rate", "事实质量-声明支撑率", True),
    ("citation_coverage", "引用品质-覆盖率", True),
    ("structure_score", "报告质量-结构评分", True),
    ("counterpoint_coverage", "报告质量-反证覆盖", True),
    ("compilation_time_ms", "生产效率-编译耗时", False),
    ("tokens_used", "生产效率-Token消耗", False),
    ("revision_rounds", "生产效率-修订轮数", False),
]

# 对比时视为 tie 的最小差值阈值
_TIE_THRESHOLD = 0.01


class ABPlatform:
    """A/B 对比平台.

    对比两份 EvaluationReport 的所有可量化维度，判定综合胜者。
    """

    def __init__(self, auto_grader=None):
        """初始化.

        Args:
            auto_grader: 可选的 AutoGrader（暂保留，供后续扩展）
        """
        self.auto_grader = auto_grader

    def compare(
        self,
        report_a: EvaluationReport,
        report_b: EvaluationReport,
        label_a: str = "A",
        label_b: str = "B",
        blind: bool = False,
    ) -> ABComparison:
        """对比两份评测报告.

        Args:
            report_a: A 侧评测报告
            report_b: B 侧评测报告
            label_a: A 侧标签
            label_b: B 侧标签
            blind: 是否盲评（标签匿名）

        Returns:
            ABComparison: 逐维度对比结果
        """
        # 盲评模式：随机交换标签
        actual_label_a = label_a
        actual_label_b = label_b
        if blind:
            seed = int(
                hashlib.md5(f"{report_a.report_id}{report_b.report_id}".encode()).hexdigest()[:8],
                16,
            )
            rng = random.Random(seed + int(time.time() * 1000) % 10000)
            if rng.choice([True, False]):
                actual_label_a, actual_label_b = label_b, label_a
                report_a, report_b = report_b, report_a

        metrics_a = report_a.metrics
        metrics_b = report_b.metrics

        dimensions: list[ABDimensionDiff] = []
        win_count = {"A": 0, "B": 0, "tie": 0}

        for field_name, display_name, higher_is_better in _COMPARABLE_DIMENSIONS:
            val_a = getattr(metrics_a, field_name, 0.0)
            val_b = getattr(metrics_b, field_name, 0.0)

            # 效率型指标取倒数再比（越小越好 → 越大越好）
            if not higher_is_better and val_a + val_b > 0:
                eps = 1e-6
                val_a_comp = 1.0 / (val_a + eps)
                val_b_comp = 1.0 / (val_b + eps)
            else:
                val_a_comp = val_a
                val_b_comp = val_b

            diff = val_b - val_a
            pct_change = (diff / max(abs(val_a), 1e-6)) * 100 if val_a != 0 else 0.0

            # 判定该维度胜者
            if val_a_comp > val_b_comp + _TIE_THRESHOLD:
                winner = "A"
            elif val_b_comp > val_a_comp + _TIE_THRESHOLD:
                winner = "B"
            else:
                winner = "tie"

            win_count[winner] += 1

            dimensions.append(
                ABDimensionDiff(
                    dimension=display_name,
                    value_a=val_a,
                    value_b=val_b,
                    diff=diff,
                    pct_change=pct_change,
                    winner=winner,
                )
            )

        # 综合胜者
        if win_count["A"] > win_count["B"]:
            overall = "A"
        elif win_count["B"] > win_count["A"]:
            overall = "B"
        else:
            overall = "tie"

        # 生成摘要
        summary = self._generate_summary(
            dimensions, overall, win_count, actual_label_a, actual_label_b
        )

        comparison = ABComparison(
            report_id_a=report_a.report_id,
            report_id_b=report_b.report_id,
            label_a=actual_label_a,
            label_b=actual_label_b,
            blind_mode=blind,
            dimensions=dimensions,
            overall_winner=overall,
            win_count=win_count,
            summary=summary,
        )

        logger.info(
            "AB comparison complete",
            winner=overall,
            blind=blind,
            dims=len(dimensions),
        )
        return comparison

    @staticmethod
    def _generate_summary(
        dimensions: list[ABDimensionDiff],
        overall: str,
        win_count: dict[str, int],
        label_a: str,
        label_b: str,
    ) -> str:
        """生成自然语言摘要."""
        a_wins = [d for d in dimensions if d.winner == "A"]
        b_wins = [d for d in dimensions if d.winner == "B"]

        parts = [f"对比结果：{label_a} vs {label_b}"]
        parts.append(f"综合胜者：{overall}（{win_count}）")

        if a_wins:
            parts.append(f"{label_a} 优势维度：{', '.join(d.dimension for d in a_wins[:3])}")
        if b_wins:
            parts.append(f"{label_b} 优势维度：{', '.join(d.dimension for d in b_wins[:3])}")

        # 关键差异
        sorted_dims = sorted(dimensions, key=lambda d: abs(d.pct_change), reverse=True)
        top = sorted_dims[:2]
        for d in top:
            parts.append(
                f"{d.dimension}: {label_a}={d.value_a:.2f}, "
                f"{label_b}={d.value_b:.2f} (差异 {d.pct_change:+.1f}%)"
            )

        return "；".join(parts)
