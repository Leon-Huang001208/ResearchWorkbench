"""表格渲染器 - 报告编译器第二阶段.

从 facts store 筛选 metric 类 FactRecord，按 entity（行）× period（列）聚合为
``TableSpec``，每个 cell 关联到具体 fact_id，使表格里的每个数字都可溯源到证据。

对应 deep-research-report.md 第二阶段"表格/图表从 facts store 渲染"。
图值必须来自 facts store，杜绝表格里的虚构数字。
"""

from typing import Optional

from core.contracts import ClaimType, FactRecord, TableSpec
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)


class TableRenderer:
    """从 FactRecord 列表渲染表格.

    只消费 claim_type==METRIC 且有 value 的 facts。按 entity 作行、period 作列
    聚合，cell 内容为 "value unit（fact_id 短码）"，便于审稿时溯源。
    """

    def render(
        self,
        facts: list[FactRecord],
        title: str = "关键指标",
        table_id: Optional[str] = None,
    ) -> Optional[TableSpec]:
        """从 facts 渲染一张指标表.

        Args:
            facts: 报告事实表
            title: 表格标题
            table_id: 表格 ID（不传则自动生成）

        Returns:
            TableSpec，若无 metric fact 返回 None
        """
        metric_facts = [
            f for f in facts if f.claim_type == ClaimType.METRIC and f.value is not None
        ]
        if not metric_facts:
            logger.debug("No metric facts to render table")
            return None

        # 收集行（entity）与列（period）
        entities: list[str] = []
        periods: list[str] = []
        seen_entities: set[str] = set()
        seen_periods: set[str] = set()
        # (entity, period) -> FactRecord
        cell_map: dict[tuple[str, str], FactRecord] = {}

        for f in metric_facts:
            entity = f.entities[0] if f.entities else "整体"
            period = f.period or "未指定"
            if entity not in seen_entities:
                seen_entities.add(entity)
                entities.append(entity)
            if period not in seen_periods:
                seen_periods.add(period)
                periods.append(period)
            # 同 entity+period 取置信度最高者
            key = (entity, period)
            existing = cell_map.get(key)
            if existing is None or f.confidence > existing.confidence:
                cell_map[key] = f

        headers = ["主体 \\ 期间", *periods]
        rows: list[list[str]] = []
        for entity in entities:
            row: list[str] = [entity]
            for period in periods:
                fact = cell_map.get((entity, period))
                row.append(self._format_cell(fact) if fact else "—")
            rows.append(row)

        table = TableSpec(
            table_id=table_id or generate_id(prefix="table"),
            title=title,
            headers=headers,
            rows=rows,
        )
        logger.info(
            "Table rendered from facts",
            table_id=table.table_id,
            entities=len(entities),
            periods=len(periods),
            cells=len(cell_map),
        )
        return table

    @staticmethod
    def _format_cell(fact: FactRecord) -> str:
        """格式化 cell：value unit [fact 短码]，便于审稿溯源."""
        value = fact.value
        unit = fact.unit or ""
        short_id = fact.fact_id[-6:] if fact.fact_id else ""
        value_str = f"{value:g}" if isinstance(value, float) else str(value)
        cell = f"{value_str} {unit}".strip()
        return f"{cell} [{short_id}]"
