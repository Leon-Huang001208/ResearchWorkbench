import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, text
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from .contracts import (
    TemporalRelation,
    IndustryChain,
    RelationshipType,
    SupplyChainPosition,
)

logger = get_logger(__name__)


class GraphRepository(BaseRepository):
    """PostgreSQL 仓储实现时间化产业链图谱持久化"""

    def add_temporal_relation(self, relation: TemporalRelation) -> TemporalRelation:
        """Add temporal relation to database"""
        query = text("""
            INSERT INTO temporal_relation (
                relation_id, from_entity_id, to_entity_id, relationship_type,
                strength, valid_from, valid_to, chain_position, industry,
                metadata, evidence_refs, created_at
            ) VALUES (
                :relation_id, :from_entity_id, :to_entity_id, :relationship_type,
                :strength, :valid_from, :valid_to, :chain_position, :industry,
                :metadata, :evidence_refs, :created_at
            )
        """)

        params = {
            "relation_id": relation.relation_id,
            "from_entity_id": relation.from_entity_id,
            "to_entity_id": relation.to_entity_id,
            "relationship_type": relation.relationship_type.value,
            "strength": relation.strength,
            "valid_from": relation.valid_from,
            "valid_to": relation.valid_to,
            "chain_position": relation.chain_position.value if relation.chain_position else None,
            "industry": relation.industry,
            "metadata": json.dumps(relation.metadata),
            "evidence_refs": json.dumps(relation.evidence_refs),
            "created_at": relation.created_at,
        }

        self.db.execute(query, params)
        self.db.commit()

        logger.debug("Added temporal relation to database", relation_id=relation.relation_id)
        return relation

    def get_temporal_relation(self, relation_id: str) -> Optional[TemporalRelation]:
        """Get temporal relation by id"""
        query = select("*").select_from(text("temporal_relation")).where(text("relation_id = :rid"))
        result = self.db.execute(query, {"rid": relation_id}).first()

        if not result:
            return None

        return self._row_to_relation(result._asdict())

    def find_relations(
        self,
        from_entity: Optional[str] = None,
        to_entity: Optional[str] = None,
        rel_type: Optional[RelationshipType] = None,
        at_time: Optional[datetime] = None,
        industry: Optional[str] = None,
    ) -> List[TemporalRelation]:
        """Find relations matching criteria"""
        conditions = []
        params = {}

        if from_entity:
            conditions.append("from_entity_id = :from_entity")
            params["from_entity"] = from_entity
        if to_entity:
            conditions.append("to_entity_id = :to_entity")
            params["to_entity"] = to_entity
        if rel_type:
            conditions.append("relationship_type = :rel_type")
            params["rel_type"] = rel_type.value
        if at_time:
            # Check if valid at given time
            conditions.append("(valid_from IS NULL OR valid_from <= :at_time)")
            params["at_time"] = at_time
            conditions.append("(valid_to IS NULL OR valid_to >= :at_time)")
        if industry:
            conditions.append("industry = :industry")
            params["industry"] = industry

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = text(f"SELECT * FROM temporal_relation {where_clause}")

        rows = self.db.execute(query, params).all()

        return [self._row_to_relation(row._asdict()) for row in rows]

    def add_industry_chain(self, chain: IndustryChain) -> IndustryChain:
        """Add industry chain to database"""
        query = text("""
            INSERT INTO industry_chain (
                chain_id, name, industry, nodes, relations, as_of, created_at
            ) VALUES (
                :chain_id, :name, :industry, :nodes, :relations, :as_of, NOW()
            )
        """)

        params = {
            "chain_id": chain.chain_id,
            "name": chain.name,
            "industry": chain.industry,
            "nodes": json.dumps(chain.nodes),
            "relations": json.dumps(chain.relations),
            "as_of": chain.as_of,
        }

        self.db.execute(query, params)
        self.db.commit()

        logger.debug("Added industry chain to database", chain_id=chain.chain_id)
        return chain

    def get_industry_chain(self, chain_id: str) -> Optional[IndustryChain]:
        """Get industry chain by id"""
        query = select("*").select_from(text("industry_chain")).where(text("chain_id = :cid"))
        result = self.db.execute(query, {"cid": chain_id}).first()

        if not result:
            return None

        row = result._asdict()
        nodes = row["nodes"] or "[]"
        if isinstance(nodes, str):
            nodes = json.loads(nodes)
        relations = row["relations"] or "[]"
        if isinstance(relations, str):
            relations = json.loads(relations)
        return IndustryChain(
            chain_id=row["chain_id"],
            name=row["name"],
            industry=row["industry"],
            nodes=nodes,
            relations=relations,
            as_of=row["as_of"],
        )

    def find_chains(self, industry: Optional[str] = None) -> List[IndustryChain]:
        """Find chains by industry"""
        if industry:
            query = text("SELECT * FROM industry_chain WHERE industry = :industry")
            params = {"industry": industry}
        else:
            query = text("SELECT * FROM industry_chain")
            params = {}

        rows = self.db.execute(query, params).all()

        results = []
        for row in rows:
            data = row._asdict()
            nodes = data["nodes"] or "[]"
            if isinstance(nodes, str):
                nodes = json.loads(nodes)
            relations = data["relations"] or "[]"
            if isinstance(relations, str):
                relations = json.loads(relations)
            results.append(IndustryChain(
                chain_id=data["chain_id"],
                name=data["name"],
                industry=data["industry"],
                nodes=nodes,
                relations=relations,
                as_of=data["as_of"],
            ))
        return results

    def _row_to_relation(self, row: dict) -> TemporalRelation:
        """Convert database row to TemporalRelation domain object"""
        from datetime import timezone

        # Handle datetime parsing from string (for SQLite)
        def parse_dt(dt_val):
            if dt_val is None:
                return None
            if isinstance(dt_val, str):
                try:
                    # Try parsing with timezone first
                    return datetime.fromisoformat(dt_val.replace(' ', 'T'))
                except ValueError:
                    # Fall back to naive datetime
                    return datetime.strptime(dt_val, '%Y-%m-%d %H:%M:%S.%f%z')
            return dt_val

        valid_from = parse_dt(row.get("valid_from"))
        if valid_from is not None and valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)

        valid_to = parse_dt(row.get("valid_to"))
        if valid_to is not None and valid_to.tzinfo is None:
            valid_to = valid_to.replace(tzinfo=timezone.utc)

        created_at = parse_dt(row.get("created_at"))
        if created_at is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        # Parse relationship type
        rel_type = RelationshipType(row["relationship_type"]) if row["relationship_type"] else None

        # Parse chain position
        chain_position = None
        if row["chain_position"]:
            chain_position = SupplyChainPosition(row["chain_position"])

        # Parse JSON fields
        metadata = row["metadata"] or "{}"
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        evidence_refs = row["evidence_refs"] or "[]"
        if isinstance(evidence_refs, str):
            evidence_refs = json.loads(evidence_refs)

        return TemporalRelation(
            relation_id=row["relation_id"],
            from_entity_id=row["from_entity_id"],
            to_entity_id=row["to_entity_id"],
            relationship_type=rel_type,
            strength=float(row["strength"]),
            valid_from=valid_from,
            valid_to=valid_to,
            chain_position=chain_position,
            industry=row["industry"],
            metadata=metadata,
            evidence_refs=evidence_refs,
            created_at=created_at,
        )
