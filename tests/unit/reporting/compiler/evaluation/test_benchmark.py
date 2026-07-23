"""Phase 3.3: test_benchmark.py — Benchmark 框架测试."""

from core.contracts import BenchmarkTask
from reporting.compiler.evaluation.benchmark_dataset import (
    BenchmarkRunner,
    BenchmarkSuite,
    create_sample_benchmark_tasks,
    create_sample_suite,
)


class TestBenchmarkTaskFactory:
    """样本任务工厂测试."""

    def test_sample_tasks_factory_returns_tasks(self):
        """create_sample_benchmark_tasks() 返回 ≥3 个任务."""
        tasks = create_sample_benchmark_tasks()
        assert len(tasks) >= 3

    def test_sample_tasks_have_required_fields(self):
        """每个任务有 task_id/prompt/category/difficulty."""
        tasks = create_sample_benchmark_tasks()
        for t in tasks:
            assert t.task_id
            assert t.prompt
            assert t.category
            assert t.difficulty in ("easy", "medium", "hard")

    def test_sample_tasks_span_categories(self):
        """覆盖多个类别."""
        tasks = create_sample_benchmark_tasks()
        categories = {t.category for t in tasks}
        assert len(categories) >= 3

    def test_sample_tasks_span_difficulties(self):
        """覆盖多个难度."""
        tasks = create_sample_benchmark_tasks()
        difficulties = {t.difficulty for t in tasks}
        assert len(difficulties) >= 2


class TestBenchmarkSuite:
    """BenchmarkSuite 测试."""

    def test_sample_suite_builds_correctly(self):
        """create_sample_suite() 返回含任务的 Suite."""
        suite = create_sample_suite()
        assert len(suite.tasks) >= 3

    def test_oversample_adds_tasks(self):
        """过采样增加任务数."""
        base_suite = create_sample_suite()
        base_count = len(base_suite.tasks)
        oversampled = create_sample_suite(oversample_category="公司研究")
        assert len(oversampled.tasks) > base_count

    def test_filter_by_category(self):
        """按类别筛选."""
        suite = create_sample_suite()
        filtered = suite.filter_by_category("公司研究")
        assert len(filtered) >= 1
        for t in filtered:
            assert t.category == "公司研究"

    def test_sample_by_difficulty(self):
        """按难度采样."""
        suite = create_sample_suite()
        easy_tasks = suite.sample(difficulty="easy")
        assert len(easy_tasks) >= 1
        for t in easy_tasks:
            assert t.difficulty == "easy"

    def test_add_task(self):
        """add() 增加任务."""
        suite = BenchmarkSuite(suite_id="test", name="test")
        task = BenchmarkTask(task_id="t1", prompt="测试", template_name="standard", category="test")
        suite.add(task)
        assert len(suite.tasks) == 1


class TestBenchmarkRunner:
    """BenchmarkRunner 测试."""

    def test_runner_empty_suite_handles_gracefully(self, stub_gateway):
        """空套件 → 优雅降级."""
        from reporting.compiler.compiler import ReportCompiler
        from reporting.compiler.evaluation.auto_grader import AutoGrader

        compiler = ReportCompiler(model_gateway=stub_gateway)
        grader = AutoGrader(model_gateway=stub_gateway)
        runner = BenchmarkRunner(compiler, grader)
        suite = BenchmarkSuite(suite_id="empty", name="empty")

        summary = runner.run_suite(suite)
        assert summary["total"] == 0

    def test_runner_run_single_integrates(self, stub_gateway):
        """run_single 完整集成."""
        from reporting.compiler.compiler import ReportCompiler
        from reporting.compiler.evaluation.auto_grader import AutoGrader

        compiler = ReportCompiler(model_gateway=stub_gateway)
        grader = AutoGrader(model_gateway=stub_gateway)
        runner = BenchmarkRunner(compiler, grader)

        task = BenchmarkTask(
            task_id="test_bm",
            prompt="分析某公司",
            template_name="standard",
            category="公司研究",
            difficulty="easy",
        )
        result = runner.run_single(task)
        assert result is not None
        report, evaluation = result
        assert report.report_id
        assert evaluation.overall_score >= 0.0
