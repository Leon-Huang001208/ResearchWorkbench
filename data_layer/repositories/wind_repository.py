"""WindRepository — Wind 数据持久化层

为 Wind Excel 适配器提供数据持久化能力，支持一致预期、融资融券、
龙虎榜和日行情数据的批量 upsert 和查询。
"""
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.observability import get_logger
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import (
    WindBlockTradeDB,
    WindConsensusEstimateDB,
    WindDailyBarDB,
    WindMarginTradingDB,
)

logger = get_logger(__name__)


class WindRepository:
    """Wind 数据仓储 —— 基于 PostgreSQL upsert 的持久化层"""

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def _upsert(self, model, records: list[dict], key_cols: list[str]) -> int:
        """通用 upsert 实现

        Args:
            model: ORM 模型类
            records: 要保存的记录列表
            key_cols: 唯一键列名列表

        Returns:
            保存的记录数
        """
        if not records:
            return 0

        session = self.db
        saved = 0
        try:
            for record in records:
                record.setdefault("source", "wind")
                stmt = pg_insert(model).values(**record)
                update_cols = {
                    k: stmt.excluded[k] for k in record if k not in key_cols and k != "id"
                }
                if update_cols:
                    stmt = stmt.on_conflict_do_update(
                        index_elements=key_cols,
                        set_=update_cols,
                    )
                else:
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=key_cols,
                    )
                session.execute(stmt)
                saved += 1
            session.commit()
            logger.info(f"WindRepository: upserted {saved} records to {model.__tablename__}")
        except Exception as e:
            session.rollback()
            logger.error(
                f"WindRepository upsert failed for {model.__tablename__}: {e}", exc_info=True
            )
            raise
        return saved

    # ─── Consensus Estimates ─────────────────────────────

    def save_consensus_estimates(self, records: list[dict]) -> int:
        """批量保存一致预期数据"""
        return self._upsert(WindConsensusEstimateDB, records, ["symbol", "trade_date", "source"])

    def get_consensus_estimates(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> list[WindConsensusEstimateDB]:
        """查询一致预期数据"""
        query = self.db.query(WindConsensusEstimateDB).filter(
            WindConsensusEstimateDB.symbol == symbol
        )
        if start_date:
            query = query.filter(WindConsensusEstimateDB.trade_date >= start_date)
        if end_date:
            query = query.filter(WindConsensusEstimateDB.trade_date <= end_date)
        return query.order_by(WindConsensusEstimateDB.trade_date.desc()).limit(limit).all()

    # ─── Margin Trading ──────────────────────────────────

    def save_margin_trading(self, records: list[dict]) -> int:
        """批量保存融资融券数据"""
        return self._upsert(WindMarginTradingDB, records, ["symbol", "trade_date", "source"])

    def get_margin_trading(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 250,
    ) -> list[WindMarginTradingDB]:
        """查询融资融券数据"""
        query = self.db.query(WindMarginTradingDB).filter(WindMarginTradingDB.symbol == symbol)
        if start_date:
            query = query.filter(WindMarginTradingDB.trade_date >= start_date)
        if end_date:
            query = query.filter(WindMarginTradingDB.trade_date <= end_date)
        return query.order_by(WindMarginTradingDB.trade_date.desc()).limit(limit).all()

    # ─── Block Trades ────────────────────────────────────

    def save_block_trades(self, records: list[dict]) -> int:
        """批量保存龙虎榜数据"""
        return self._upsert(WindBlockTradeDB, records, ["symbol", "trade_date", "source"])

    def get_block_trades(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 250,
    ) -> list[WindBlockTradeDB]:
        """查询龙虎榜数据"""
        query = self.db.query(WindBlockTradeDB).filter(WindBlockTradeDB.symbol == symbol)
        if start_date:
            query = query.filter(WindBlockTradeDB.trade_date >= start_date)
        if end_date:
            query = query.filter(WindBlockTradeDB.trade_date <= end_date)
        return query.order_by(WindBlockTradeDB.trade_date.desc()).limit(limit).all()

    # ─── Daily Bars ──────────────────────────────────────

    def save_daily_bars(self, records: list[dict]) -> int:
        """批量保存日行情数据"""
        return self._upsert(WindDailyBarDB, records, ["symbol", "trade_date", "source"])

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 500,
    ) -> list[WindDailyBarDB]:
        """查询日行情数据"""
        query = self.db.query(WindDailyBarDB).filter(WindDailyBarDB.symbol == symbol)
        if start_date:
            query = query.filter(WindDailyBarDB.trade_date >= start_date)
        if end_date:
            query = query.filter(WindDailyBarDB.trade_date <= end_date)
        return query.order_by(WindDailyBarDB.trade_date.desc()).limit(limit).all()

    def close(self):
        """关闭数据库会话"""
        if self._db:
            self._db.close()
            self._db = None
