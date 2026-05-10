"""组合提案仓储实现"""
from typing import List, Optional


from core.contracts.portfolio import PortfolioCandidate, PortfolioProposal
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import PortfolioProposalDB

logger = get_logger(__name__)


class PortfolioRepositoryImpl(BaseRepository):
    """组合提案仓储实现"""

    def save_proposal(self, proposal: PortfolioProposal) -> PortfolioProposal:
        """保存组合提案"""
        existing = (
            self.db.query(PortfolioProposalDB)
            .filter_by(proposal_id=proposal.proposal_id)
            .first()
        )
        if existing:
            existing.name = proposal.name
            existing.candidates = [c.model_dump() for c in proposal.candidates]
            existing.allocations = proposal.allocations
            existing.constraints_applied = proposal.constraints_applied
            existing.excluded_signals = proposal.excluded_signals
            existing.rationale = proposal.rationale
            db_proposal = existing
        else:
            db_proposal = PortfolioProposalDB(
                proposal_id=proposal.proposal_id,
                name=proposal.name,
                candidates=[c.model_dump() for c in proposal.candidates],
                allocations=proposal.allocations,
                constraints_applied=proposal.constraints_applied,
                excluded_signals=proposal.excluded_signals,
                rationale=proposal.rationale,
            )
            self.db.add(db_proposal)
        self.db.flush()
        logger.info("proposal saved", proposal_id=proposal.proposal_id)
        return self._to_domain(db_proposal)

    def get_proposal(self, proposal_id: str) -> Optional[PortfolioProposal]:
        """获取组合提案"""
        db_proposal = (
            self.db.query(PortfolioProposalDB)
            .filter(PortfolioProposalDB.proposal_id == proposal_id)
            .first()
        )
        if not db_proposal:
            return None
        return self._to_domain(db_proposal)

    def list_proposals(self, limit: int = 100) -> List[PortfolioProposal]:
        """列出历史提案"""
        db_proposals = (
            self.db.query(PortfolioProposalDB)
            .order_by(PortfolioProposalDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_domain(p) for p in db_proposals]

    def _to_domain(self, db_proposal: PortfolioProposalDB) -> PortfolioProposal:
        """转换为领域模型"""
        candidates = [
            PortfolioCandidate(**c) for c in db_proposal.candidates
        ]
        return PortfolioProposal(
            proposal_id=db_proposal.proposal_id,
            name=db_proposal.name,
            created_at=db_proposal.created_at,
            candidates=candidates,
            allocations=db_proposal.allocations,
            constraints_applied=db_proposal.constraints_applied,
            excluded_signals=db_proposal.excluded_signals,
            rationale=db_proposal.rationale,
        )
