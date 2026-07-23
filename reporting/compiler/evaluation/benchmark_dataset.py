"""
基准测试框架 - 报告编译器第三阶段 3.3.

提供 BenchmarkSuite（任务集合）、BenchmarkRunner（编译+评测+聚合），
以及 sample factories 用于快速创建 10-15 个样本任务。

BenchmarkTask 定义一次报告生成与评测的输入与期望，
不包含完整 golden dataset（数据策展工作在后续阶段）。
"""

import statistics

from core.contracts import BenchmarkTask, CompiledReport, EvaluationReport, ReportTask
from core.observability import get_logger

logger = get_logger(__name__)

# ── 样本工厂 ────────────────────────────────────────────────────────────

SAMPLE_CATEGORIES = ["公司研究", "行业分析", "竞品对比", "市场格局", "技术路线"]


def create_sample_benchmark_tasks() -> list[BenchmarkTask]:
    """创建 12 个样本 BenchmarkTask，覆盖不同类别与难度.

    Returns:
        list[BenchmarkTask]: 样本任务列表
    """
    tasks: list[BenchmarkTask] = []
    base_prompts: list[tuple[str, str, str, list[str], int]] = [
        # (task_id, prompt, category, expected_sections, golden_facts_count)
        (
            "bm_easy_01",
            "分析贵州茅台2024年财务表现",
            "公司研究",
            ["营收分析", "利润分析", "风险提示"],
            5,
        ),
        (
            "bm_easy_02",
            "宁德时代动力电池业务分析",
            "公司研究",
            ["业务概览", "产能分析", "竞争格局"],
            4,
        ),
        (
            "bm_easy_03",
            "人工智能产业链上游芯片环节分析",
            "行业分析",
            ["产业链概览", "芯片环节", "投资机会"],
            6,
        ),
        (
            "bm_easy_04",
            "光模块行业2024年回顾与展望",
            "行业分析",
            ["行业概览", "市场规模", "主要厂商", "展望"],
            5,
        ),
        (
            "bm_med_01",
            "中际旭创vs新易盛光模块业务对比",
            "竞品对比",
            ["公司简介", "营收对比", "毛利率对比", "产能对比", "技术路线"],
            8,
        ),
        (
            "bm_med_02",
            "比亚迪与特斯拉中国市场竞争力对比",
            "竞品对比",
            ["市场定位", "产品矩阵", "销量对比", "成本优势", "风险"],
            8,
        ),
        (
            "bm_med_03",
            "光伏产业链竞争格局分析",
            "市场格局",
            ["产业链概览", "硅料环节", "硅片环节", "电池片环节", "组件环节"],
            10,
        ),
        (
            "bm_med_04",
            "半导体设备国产替代现状",
            "技术路线",
            ["行业背景", "关键设备", "国产化率", "主要企业", "政策与展望"],
            7,
        ),
        (
            "bm_hard_01",
            "CPO共封装光学技术路线与硅光之争",
            "技术路线",
            ["技术背景", "CPO方案", "硅光方案", "对比分析", "产业化进度", "投资建议"],
            10,
        ),
        (
            "bm_hard_02",
            "HBM高带宽存储产业链全景分析",
            "行业分析",
            ["产品概述", "市场规模", "上游材料", "制造工艺", "主要厂商", "国产替代", "展望"],
            10,
        ),
        (
            "bm_hard_03",
            "AI算力需求驱动的数据中心架构变革",
            "市场格局",
            ["行业背景", "算力需求", "光互联", "交换机", "液冷", "投资机会"],
            10,
        ),
        (
            "bm_hard_04",
            "人形机器人核心零部件供应链深度研究",
            "技术路线",
            ["行业概览", "执行器", "传感器", "减速器", "主要企业", "国产化", "展望"],
            10,
        ),
    ]

    for task_id, prompt, category, expected_sections, golden_count in base_prompts:
        difficulty = (
            "easy"
            if task_id.startswith("bm_easy")
            else ("medium" if task_id.startswith("bm_med") else "hard")
        )
        tasks.append(
            BenchmarkTask(
                task_id=task_id,
                prompt=prompt,
                template_name="standard",
                expected_sections=expected_sections,
                golden_facts_count=golden_count,
                category=category,
                difficulty=difficulty,
            )
        )

    logger.info("Sample benchmark tasks created", count=len(tasks))
    return tasks


def create_sample_suite(oversample_category: str | None = None) -> "BenchmarkSuite":
    """创建含样本任务的 BenchmarkSuite.

    Args:
        oversample_category: 如需对某类别过采样，指定类别名

    Returns:
        BenchmarkSuite
    """
    tasks = create_sample_benchmark_tasks()
    if oversample_category:
        extra = [t for t in tasks if t.category == oversample_category]
        tasks.extend(extra)
    suite = BenchmarkSuite(name="sample_suite", tasks=tasks)
    suite.suite_id = "sample_suite"
    return suite


# ── BenchmarkSuite ───────────────────────────────────────────────────────


class BenchmarkSuite:
    """基准测试套件 — 管理 BenchmarkTask 集合.

    支持按类别/难度筛选与采样。
    """

    def __init__(
        self,
        suite_id: str = "",
        name: str = "",
        tasks: list[BenchmarkTask] | None = None,
        description: str = "",
    ):
        self.suite_id = suite_id
        self.name = name
        self.tasks: list[BenchmarkTask] = tasks or []
        self.description = description

    def add(self, task: BenchmarkTask) -> None:
        """添加任务."""
        self.tasks.append(task)

    def sample(
        self,
        n: int | None = None,
        category: str | None = None,
        difficulty: str | None = None,
    ) -> list[BenchmarkTask]:
        """按条件采样.

        Args:
            n: 返回数量上限
            category: 按类别筛选
            difficulty: 按难度筛选
        """
        filtered = self.tasks
        if category:
            filtered = [t for t in filtered if t.category == category]
        if difficulty:
            filtered = [t for t in filtered if t.difficulty == difficulty]
        if n is not None:
            filtered = filtered[:n]
        return filtered

    def filter_by_category(self, category: str) -> list[BenchmarkTask]:
        """按类别筛选."""
        return [t for t in self.tasks if t.category == category]

    def __len__(self) -> int:
        return len(self.tasks)

    def __iter__(self):
        return iter(self.tasks)


# ── BenchmarkRunner ──────────────────────────────────────────────────────


class BenchmarkRunner:
    """基准测试运行器 — 编译+评测+聚合.

    对 BenchmarkSuite 中的每个任务执行 compiler.compile() + auto_grader.grade()，
    汇总为聚合统计。
    """

    def __init__(self, compiler, auto_grader):
        """初始化.

        Args:
            compiler: ReportCompiler 实例
            auto_grader: AutoGrader 实例
        """
        self.compiler = compiler
        self.auto_grader = auto_grader

    def run_single(self, task: BenchmarkTask) -> tuple[CompiledReport, EvaluationReport] | None:
        """运行单个任务.

        Args:
            task: 基准任务

        Returns:
            (CompiledReport, EvaluationReport) 或 None（失败时）
        """
        report_task = ReportTask(
            task_id=task.task_id,
            prompt=task.prompt,
            template_name=task.template_name,
        )
        try:
            report = self.compiler.compile(report_task)
            evaluation = self.auto_grader.grade(report)
            logger.info(
                "Benchmark task complete", task_id=task.task_id, score=evaluation.overall_score
            )
            return report, evaluation
        except Exception as e:
            logger.error("Benchmark task failed", task_id=task.task_id, error=str(e))
            return None

    def run_suite(self, suite: BenchmarkSuite) -> dict:
        """运行完整套件，返回聚合统计.

        Args:
            suite: 基准测试套件

        Returns:
            dict: 含 scores / mean / median / std / grade_dist / category_avg
        """
        results: list[tuple[CompiledReport, EvaluationReport]] = []
        for task in suite.tasks:
            result = self.run_single(task)
            if result is not None:
                results.append(result)

        if not results:
            logger.warning("No benchmark tasks completed successfully")
            return {
                "total": 0,
                "scores": [],
                "mean": 0.0,
                "median": 0.0,
                "std": 0.0,
                "grade_distribution": {},
                "per_category_averages": {},
            }

        scores = [r[1].overall_score for r in results]
        mean_score = statistics.mean(scores)
        median_score = statistics.median(scores)
        std_score = statistics.stdev(scores) if len(scores) >= 2 else 0.0

        # Grade distribution
        grade_dist: dict[str, int] = {}
        for r in results:
            g = r[1].grade
            grade_dist[g] = grade_dist.get(g, 0) + 1

        # Per-category averages
        cat_scores: dict[str, list[float]] = {}
        for task in suite.tasks:
            for report, evaluation in results:
                if evaluation.report_id == task.task_id:
                    # Not exact match — use task lookup
                    pass

        # Category from task → score
        for i, task in enumerate(suite.tasks):
            if i < len(results) and results[i] is not None:
                cat = task.category
                if cat not in cat_scores:
                    cat_scores[cat] = []
                cat_scores[cat].append(results[i][1].overall_score)

        per_category = {cat: statistics.mean(vals) for cat, vals in cat_scores.items() if vals}

        summary = {
            "total": len(results),
            "scores": scores,
            "mean": mean_score,
            "median": median_score,
            "std": std_score,
            "grade_distribution": grade_dist,
            "per_category_averages": per_category,
        }

        logger.info(
            "Benchmark suite complete", **{k: v for k, v in summary.items() if k != "scores"}
        )
        return summary
