from typing import List, Optional

from core.contracts import CanonicalId
from core.interfaces import EntityRepository
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import Entity as EntityModel

logger = get_logger(__name__)


class EntityRepositoryImpl(BaseRepository, EntityRepository):
    """实体仓储实现"""

    def _to_domain(self, model: EntityModel) -> CanonicalId:
        """转换为领域模型"""
        return CanonicalId(
            canonical_id=model.canonical_id,
            asset_type=model.entity_type,
            market=model.properties.get("market", ""),
            venue=model.properties.get("venue", ""),
            symbol=model.properties.get("symbol", ""),
            vendor_ids=model.vendor_ids,
            name_zh=model.properties.get("name_zh"),
            name_en=model.properties.get("name_en"),
        )

    def _to_model(self, domain: CanonicalId) -> EntityModel:
        """转换为数据库模型"""
        return EntityModel(
            entity_id=domain.canonical_id,
            canonical_id=domain.canonical_id,
            entity_type=domain.asset_type,
            canonical_name=domain.name_zh or domain.name_en or domain.symbol,
            vendor_ids=domain.vendor_ids,
            properties={
                "market": domain.market,
                "venue": domain.venue,
                "symbol": domain.symbol,
                "name_zh": domain.name_zh,
                "name_en": domain.name_en,
            },
        )

    def save(self, entity: CanonicalId) -> CanonicalId:
        """保存实体"""
        model = self.db.query(EntityModel).filter_by(canonical_id=entity.canonical_id).first()
        if model:
            model.entity_type = entity.asset_type
            model.canonical_name = entity.name_zh or entity.name_en or entity.symbol
            model.vendor_ids = entity.vendor_ids
            model.properties = {
                "market": entity.market,
                "venue": entity.venue,
                "symbol": entity.symbol,
                "name_zh": entity.name_zh,
                "name_en": entity.name_en,
            }
        else:
            model = self._to_model(entity)
            self.db.add(model)
        self.db.flush()
        logger.debug("entity saved", canonical_id=entity.canonical_id)
        return self._to_domain(model)

    def get(self, id: str) -> Optional[CanonicalId]:
        """根据 ID 获取实体"""
        model = self.db.query(EntityModel).filter_by(entity_id=id).first()
        return self._to_domain(model) if model else None

    def list(self, limit: int = 100, offset: int = 0) -> List[CanonicalId]:
        """列出实体"""
        models = self.db.query(EntityModel).limit(limit).offset(offset).all()
        return [self._to_domain(m) for m in models]

    def delete(self, id: str) -> bool:
        """删除实体"""
        count = self.db.query(EntityModel).filter_by(entity_id=id).delete()
        return count > 0

    def get_by_symbol(self, symbol: str, venue: str) -> Optional[CanonicalId]:
        """根据代码和交易所获取实体"""
        # 查询 properties 中的 symbol 和 venue
        models = self.db.query(EntityModel).all()
        for m in models:
            if m.properties.get("symbol") == symbol and m.properties.get("venue") == venue:
                return self._to_domain(m)
        return None

    def search(self, query: str) -> List[CanonicalId]:
        """搜索实体"""
        results = []
        models = self.db.query(EntityModel).all()
        query_lower = query.lower()
        for m in models:
            if (
                query_lower in m.canonical_name.lower()
                or query_lower in str(m.properties.get("symbol", "")).lower()
            ):
                results.append(self._to_domain(m))
        return results
