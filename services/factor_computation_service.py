"""FactorComputationService — 定时因子计算服务

编排完整的因子研究闭环：
  1. 从 FactorStore 加载定义和值
  2. 构建横截面因子矩阵
  3. 评估因子预测能力 (IC, RankIC, decile spread)
  4. 拟合动态权重
  5. 结果持久化回 FactorStore

可由 CrawlScheduler 或其他定时任务调用。
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from core.contracts.factors import FactorDefinition, FactorValue
from core.observability import get_logger
from services.factor_store_service import FactorStore
from signal_lab.factors.evaluation import FactorEvaluator
from signal_lab.factors.matrix import FactorMatrixBuilder
from signal_lab.factors.models import RollingICWeightedModel

logger = get_logger(__name__)


class FactorComputationService:
    """编排因子计算与评估的定时服务

    用法::

        service = FactorComputationService()
        result = service.run_daily_cycle(as_of_date=date.today())
    """

    def __init__(
        self,
        store: FactorStore | None = None,
        evaluator: FactorEvaluator | None = None,
        model: RollingICWeightedModel | None = None,
    ):
        self.store = store or FactorStore()
        self.evaluator = evaluator or FactorEvaluator(horizon_days=20)
        self.model = model or RollingICWeightedModel(
            lookback_periods=12,
            metric="rank_ic",
        )

    def run_daily_cycle(
        self,
        as_of_date: date,
        factor_ids: list[str] | None = None,
        forward_returns: pd.Series | pd.DataFrame | None = None,
    ) -> dict:
        """运行单日因子研究循环

        1. 获取因子定义
        2. 加载因子值 → 构建横截面矩阵
        3. 评估因子 → 存储评估结果
        4. 拟合动态权重 → 存储权重快照

        Args:
            as_of_date: 计算日期
            factor_ids: 可选，限制参与计算的因子
            forward_returns: 可选，前向收益（用于评估）。如果为 None 则跳过评估步骤。

        Returns:
            包含步骤摘要的 dict
        """
        started_at = datetime.utcnow()
        summary: dict = {
            "as_of_date": as_of_date.isoformat(),
            "started_at": started_at.isoformat(),
            "steps": {},
        }

        # Step 1: 加载因子定义
        definitions = self.store.get_definitions(factor_ids=factor_ids)
        if not definitions:
            logger.warning("No factor definitions found, skipping cycle")
            summary["status"] = "skipped_no_definitions"
            return summary
        summary["steps"]["definitions_loaded"] = len(definitions)

        # Step 2: 加载因子值 → 构建横截面矩阵
        values = self.store.load_values(
            as_of_date=as_of_date,
            factor_ids=factor_ids,
        )
        summary["steps"]["values_loaded"] = len(values)

        if not values:
            logger.warning("No factor values for %s, skipping cycle", as_of_date)
            summary["status"] = "skipped_no_values"
            return summary

        matrix = self._build_matrix(definitions, values, as_of_date)
        summary["steps"]["matrix_shape"] = list(matrix.shape)

        # Step 3: 评估因子
        if forward_returns is not None:
            evaluations = self.evaluator.evaluate(
                factor_matrix=matrix,
                forward_returns=forward_returns,
                as_of_date=as_of_date,
                factor_ids=list(matrix.columns),
            )
            if evaluations:
                self.store.store_evaluations(evaluations)
                summary["steps"]["evaluations_stored"] = len(evaluations)
                logger.info(
                    "Factor evaluations stored for %s: %d factors",
                    as_of_date,
                    len(evaluations),
                )
            else:
                summary["steps"]["evaluations_stored"] = 0
        else:
            # 尝试用历史评估拟合权重
            evaluations = self.store.load_latest_evaluations(
                factor_ids=factor_ids,
                horizon_days=self.evaluator.horizon_days,
            )
            summary["steps"]["evaluations_loaded_from_history"] = len(evaluations)

        # Step 4: 拟合动态权重
        if evaluations:
            weights = self.model.fit(evaluations, as_of_date=as_of_date)
            self.store.store_weights(weights)
            summary["steps"]["weights_stored"] = 1
            summary["steps"]["active_factors"] = len(weights.weights)
            logger.info(
                "Dynamic weights fitted for %s: %d active factors",
                as_of_date,
                len(weights.weights),
            )
        else:
            summary["steps"]["weights_stored"] = 0
            logger.warning("No evaluations available for weight fitting on %s", as_of_date)

        completed_at = datetime.utcnow()
        summary["completed_at"] = completed_at.isoformat()
        summary["duration_seconds"] = (completed_at - started_at).total_seconds()
        summary["status"] = "completed"
        return summary

    def _build_matrix(
        self,
        definitions: list[FactorDefinition],
        values: list[FactorValue],
        as_of_date: date,
    ) -> pd.DataFrame:
        builder = FactorMatrixBuilder(definitions)
        return builder.build(values=values, as_of_date=as_of_date)

    def close(self):
        """释放资源"""
        self.store.close()
