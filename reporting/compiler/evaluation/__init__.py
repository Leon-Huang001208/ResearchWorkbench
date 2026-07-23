"""
评测体系 - 报告编译器第三阶段 3.3.

从原子声明抽取到多维度评分到 A/B 对比的完整评测闭环。

模块：
- claim_extractor: 从报告正文拆解 AtomicClaim
- metrics: 五维度 ReportMetrics 计算
- auto_grader: 编排评测管线，产出 EvaluationReport
- benchmark_dataset: BenchmarkSuite + BenchmarkRunner
- ab_platform: A/B 对比
"""

from reporting.compiler.evaluation.ab_platform import ABPlatform
from reporting.compiler.evaluation.auto_grader import AutoGrader
from reporting.compiler.evaluation.benchmark_dataset import (
    BenchmarkRunner,
    BenchmarkSuite,
    create_sample_benchmark_tasks,
    create_sample_suite,
)
from reporting.compiler.evaluation.claim_extractor import ClaimExtractor
from reporting.compiler.evaluation.metrics import MetricsComputer

__all__ = [
    "ABPlatform",
    "AutoGrader",
    "BenchmarkRunner",
    "BenchmarkSuite",
    "ClaimExtractor",
    "MetricsComputer",
    "create_sample_benchmark_tasks",
    "create_sample_suite",
]
