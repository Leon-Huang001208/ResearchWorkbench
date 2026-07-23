"""图表渲染器 - 报告编译器第二阶段.

从 facts store 筛选数值型 FactRecord，按 entity 聚合为 ``ChartSpec``。
图值必须来自 facts store，杜绝图表里的虚构数字。

对应 deep-research-report.md 第二阶段"表格/图表从 facts store 渲染"。

注意：第二阶段不改 reporting/projections/。ChartSpec.data_range 在编译器场景
没有 Excel range，这里存 JSON 序列化的数值序列与 fact_id，供后续 projection 层
或审稿 UI 消费。projection 层的真正画图逻辑留待迁移期接入。
"""

import json
from typing import Optional

from core.contracts import ChartSpec, ClaimType, FactRecord
from core.observability import get_logger
from core.utils.id_gen import generate_id

logger = get_logger(__name__)


class ChartRenderer:
    """从 FactRecord 列表渲染图表 spec.

    按 entity 聚合数值型 metric facts，每个 entity 一条序列，
    产出柱状图（多 entity 对比）或折线图（单 entity 时间序列）。
    """

    def render(
        self,
        facts: list[FactRecord],
        title: str = "关键指标对比",
        chart_id: Optional[str] = None,
    ) -> Optional[ChartSpec]:
        """从 facts 渲染一张图表.

        Args:
            facts: 报告事实表
            title: 图表标题
            chart_id: 图表 ID（不传则自动生成）

        Returns:
            ChartSpec，若无可用数值型 fact 返回 None
        """
        numeric_facts = [
            f for f in facts if f.claim_type == ClaimType.METRIC and f.value is not None
        ]
        if not numeric_facts:
            logger.debug("No numeric facts to render chart")
            return None

        # 按 entity 聚合
        by_entity: dict[str, list[FactRecord]] = {}
        for f in numeric_facts:
            entity = f.entities[0] if f.entities else "整体"
            by_entity.setdefault(entity, []).append(f)

        # 序列数据：每个 entity 的 (period, value, fact_id)
        series = []
        for entity, entity_facts in by_entity.items():
            # 按 period 排序（若有）
            sorted_facts = sorted(entity_facts, key=lambda x: x.period or "")
            series.append(
                {
                    "entity": entity,
                    "values": [
                        {
                            "period": f.period or "",
                            "value": f.value,
                            "unit": f.unit or "",
                            "fact_id": f.fact_id,
                        }
                        for f in sorted_facts
                    ],
                }
            )

        chart_type = "line" if len(by_entity) == 1 else "bar"
        spec = ChartSpec(
            chart_id=chart_id or generate_id(prefix="chart"),
            chart_type=chart_type,  # type: ignore[arg-type]
            title=title,
            data_range=json.dumps(series, ensure_ascii=False),
        )
        logger.info(
            "Chart rendered from facts",
            chart_id=spec.chart_id,
            chart_type=chart_type,
            entities=len(by_entity),
            points=sum(len(s["values"]) for s in series),
        )
        return spec
