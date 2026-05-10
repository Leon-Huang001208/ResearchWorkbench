"""Paper Trading 持久化仓储实现"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.contracts.paper_trading import (
    BenchmarkComparison,
    PaperPortfolio,
    PerformanceMetrics,
    PortfolioSnapshot,
    RebalanceEvent,
    SimulationAssumptions,
    SimulationMode,
    SimulationResult,
)
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import PaperPortfolioDB, SimulationResultDB

logger = get_logger(__name__)


class PaperTradingRepositoryImpl(BaseRepository):
    """Paper Trading 仓储实现"""

    # ── PaperPortfolio CRUD ──────────────────────────────

    def save_paper_portfolio(self, portfolio: PaperPortfolio) -> PaperPortfolio:
        """保存模拟组合"""
        existing = (
            self.db.query(PaperPortfolioDB).filter_by(portfolio_id=portfolio.portfolio_id).first()
        )

        data = self._portfolio_to_dict(portfolio)

        if existing:
            existing.name = portfolio.name
            existing.proposal_id = portfolio.proposal_id
            existing.status = portfolio.status
            existing.assumptions = data["assumptions"]
            existing.current_snapshot = data["current_snapshot"]
            existing.snapshots = data["snapshots"]
            existing.rebalance_events = data["rebalance_events"]
            existing.portfolio_metadata = data["metadata"]
            db_obj = existing
        else:
            db_obj = PaperPortfolioDB(
                portfolio_id=portfolio.portfolio_id,
                proposal_id=portfolio.proposal_id,
                name=portfolio.name,
                status=portfolio.status,
                assumptions=data["assumptions"],
                current_snapshot=data["current_snapshot"],
                snapshots=data["snapshots"],
                rebalance_events=data["rebalance_events"],
                portfolio_metadata=data["metadata"],
            )
            self.db.add(db_obj)

        self.db.flush()
        logger.info("paper portfolio saved", portfolio_id=portfolio.portfolio_id)
        return self._dict_to_portfolio(self._db_to_dict(db_obj))

    def get_paper_portfolio(self, portfolio_id: str) -> Optional[PaperPortfolio]:
        """获取模拟组合"""
        db_obj = (
            self.db.query(PaperPortfolioDB)
            .filter(PaperPortfolioDB.portfolio_id == portfolio_id)
            .first()
        )
        if not db_obj:
            return None
        return self._dict_to_portfolio(self._db_to_dict(db_obj))

    def list_paper_portfolios(self, limit: int = 100) -> List[PaperPortfolio]:
        """列出模拟组合"""
        db_objs = (
            self.db.query(PaperPortfolioDB)
            .order_by(PaperPortfolioDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._dict_to_portfolio(self._db_to_dict(o)) for o in db_objs]

    # ── SimulationResult CRUD ────────────────────────────

    def save_simulation_result(self, result: SimulationResult) -> SimulationResult:
        """保存模拟结果"""
        existing = self.db.query(SimulationResultDB).filter_by(result_id=result.result_id).first()

        data = self._result_to_dict(result)

        if existing:
            existing.name = result.name
            existing.mode = result.mode.value
            existing.assumptions = data["assumptions"]
            existing.performance = data["performance"]
            existing.benchmark_comparisons = data["benchmark_comparisons"]
            existing.nav_series = data["nav_series"]
            existing.rebalance_count = result.rebalance_count
            existing.total_turnover = result.total_turnover
            existing.result_metadata = data["metadata"]
            db_obj = existing
        else:
            db_obj = SimulationResultDB(
                result_id=result.result_id,
                portfolio_id=result.portfolio_id,
                name=result.name,
                mode=result.mode.value,
                assumptions=data["assumptions"],
                performance=data["performance"],
                benchmark_comparisons=data["benchmark_comparisons"],
                nav_series=data["nav_series"],
                rebalance_count=result.rebalance_count,
                total_turnover=result.total_turnover,
                result_metadata=data["metadata"],
            )
            self.db.add(db_obj)

        self.db.flush()
        logger.info("simulation result saved", result_id=result.result_id)
        return self._dict_to_result(self._db_result_to_dict(db_obj))

    def get_simulation_result(self, result_id: str) -> Optional[SimulationResult]:
        """获取模拟结果"""
        db_obj = (
            self.db.query(SimulationResultDB)
            .filter(SimulationResultDB.result_id == result_id)
            .first()
        )
        if not db_obj:
            return None
        return self._dict_to_result(self._db_result_to_dict(db_obj))

    def list_simulation_results(
        self,
        portfolio_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[SimulationResult]:
        """列出模拟结果"""
        query = self.db.query(SimulationResultDB)
        if portfolio_id:
            query = query.filter(SimulationResultDB.portfolio_id == portfolio_id)
        db_objs = query.order_by(SimulationResultDB.created_at.desc()).limit(limit).all()
        return [self._dict_to_result(self._db_result_to_dict(o)) for o in db_objs]

    # ── 序列化辅助 ──────────────────────────────────────

    def _portfolio_to_dict(self, portfolio: PaperPortfolio) -> Dict[str, Any]:
        """PaperPortfolio → 可序列化字典"""
        return {
            "portfolio_id": portfolio.portfolio_id,
            "proposal_id": portfolio.proposal_id,
            "name": portfolio.name,
            "status": portfolio.status,
            "assumptions": portfolio.assumptions.model_dump(mode="json"),
            "current_snapshot": (
                portfolio.current_snapshot.model_dump(mode="json")
                if portfolio.current_snapshot
                else None
            ),
            "snapshots": [s.model_dump(mode="json") for s in portfolio.snapshots],
            "rebalance_events": [e.model_dump(mode="json") for e in portfolio.rebalance_events],
            "metadata": portfolio.metadata,
        }

    def _db_to_dict(self, db_obj: PaperPortfolioDB) -> Dict[str, Any]:
        """PaperPortfolioDB → 字典"""
        return {
            "portfolio_id": db_obj.portfolio_id,
            "proposal_id": db_obj.proposal_id,
            "name": db_obj.name,
            "status": db_obj.status,
            "assumptions": db_obj.assumptions or {},
            "current_snapshot": db_obj.current_snapshot,
            "snapshots": db_obj.snapshots or [],
            "rebalance_events": db_obj.rebalance_events or [],
            "metadata": db_obj.portfolio_metadata or {},
            "created_at": db_obj.created_at,
        }

    def _dict_to_portfolio(self, data: Dict[str, Any]) -> PaperPortfolio:
        """字典 → PaperPortfolio"""
        assumptions = (
            SimulationAssumptions(**data["assumptions"])
            if data.get("assumptions")
            else SimulationAssumptions()
        )

        current_snapshot = None
        if data.get("current_snapshot"):
            current_snapshot = PortfolioSnapshot(**data["current_snapshot"])

        snapshots = [PortfolioSnapshot(**s) for s in data.get("snapshots", [])]
        rebalance_events = [RebalanceEvent(**e) for e in data.get("rebalance_events", [])]

        return PaperPortfolio(
            portfolio_id=data["portfolio_id"],
            proposal_id=data["proposal_id"],
            name=data["name"],
            created_at=data["created_at"],
            assumptions=assumptions,
            status=data.get("status", "active"),
            current_snapshot=current_snapshot,
            snapshots=snapshots,
            rebalance_events=rebalance_events,
            metadata=data.get("metadata", {}),
        )

    def _result_to_dict(self, result: SimulationResult) -> Dict[str, Any]:
        """SimulationResult → 可序列化字典"""
        return {
            "result_id": result.result_id,
            "portfolio_id": result.portfolio_id,
            "name": result.name,
            "mode": result.mode.value,
            "assumptions": result.assumptions.model_dump(mode="json"),
            "performance": result.performance.model_dump(mode="json"),
            "benchmark_comparisons": [
                b.model_dump(mode="json") for b in result.benchmark_comparisons
            ],
            "nav_series": result.nav_series,
            "rebalance_count": result.rebalance_count,
            "total_turnover": result.total_turnover,
            "metadata": result.metadata,
        }

    def _db_result_to_dict(self, db_obj: SimulationResultDB) -> Dict[str, Any]:
        """SimulationResultDB → 字典"""
        return {
            "result_id": db_obj.result_id,
            "portfolio_id": db_obj.portfolio_id,
            "name": db_obj.name,
            "mode": db_obj.mode,
            "assumptions": db_obj.assumptions or {},
            "performance": db_obj.performance or {},
            "benchmark_comparisons": db_obj.benchmark_comparisons or [],
            "nav_series": db_obj.nav_series or [],
            "rebalance_count": db_obj.rebalance_count,
            "total_turnover": float(db_obj.total_turnover),
            "metadata": db_obj.result_metadata or {},
            "created_at": db_obj.created_at,
        }

    def _dict_to_result(self, data: Dict[str, Any]) -> SimulationResult:
        """字典 → SimulationResult"""
        performance = (
            PerformanceMetrics(**data["performance"])
            if data.get("performance")
            else PerformanceMetrics(
                start_date=data.get("created_at", datetime.now(timezone.utc)),
                end_date=data.get("created_at", datetime.now(timezone.utc)),
            )
        )

        benchmark_comparisons = [
            BenchmarkComparison(**b) for b in data.get("benchmark_comparisons", [])
        ]

        assumptions = (
            SimulationAssumptions(**data["assumptions"])
            if data.get("assumptions")
            else SimulationAssumptions()
        )

        return SimulationResult(
            result_id=data["result_id"],
            portfolio_id=data["portfolio_id"],
            name=data["name"],
            created_at=data["created_at"],
            mode=SimulationMode(data.get("mode", "replay")),
            assumptions=assumptions,
            performance=performance,
            benchmark_comparisons=benchmark_comparisons,
            nav_series=data.get("nav_series", []),
            rebalance_count=data.get("rebalance_count", 0),
            total_turnover=data.get("total_turnover", 0.0),
            metadata=data.get("metadata", {}),
        )
