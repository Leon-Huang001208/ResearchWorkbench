"""
Thesis Review Service - Evidence-driven Bull/Bear/Skeptic structured review framework
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from core.contracts import (
    CognitiveBlackboard,
    ConflictDetectionSummary,
    EvidenceReference,
    ReviewCard,
    ReviewPosition,
    ThesisCard,
)
from core.observability import get_logger

logger = get_logger(__name__)


class ThesisReviewService:
    """Service for generating structured Bull/Bear/Skeptic reviews for investment theses"""

    def __init__(self):
        logger.info("ThesisReviewService initialized")

    def generate_bull_review(
        self,
        thesis: ThesisCard,
        evidence_list: List[EvidenceReference],
    ) -> ReviewCard:
        """Generate Bull case review for the thesis"""
        bull_review = ReviewCard(
            review_id=str(uuid4()),
            thesis_id=thesis.thesis_id,
            position=ReviewPosition.BULL,
            summary=f"Bull case for {thesis.target_name} based on {thesis.event_summary}",
            evidence_refs=[e for e in evidence_list if e.confidence_in_evidence > 0.5],
            confidence_score=self._calculate_bull_confidence(thesis, evidence_list),
            reasoning_chain=self._generate_bull_reasoning(thesis, evidence_list),
            invalidation_triggers=self._extract_invalidation_triggers(thesis, ReviewPosition.BULL),
            created_at=datetime.utcnow().isoformat(),
        )
        logger.debug(
            f"Generated bull review: {bull_review.review_id} for thesis {thesis.thesis_id}"
        )
        return bull_review

    def generate_bear_review(
        self,
        thesis: ThesisCard,
        evidence_list: List[EvidenceReference],
    ) -> ReviewCard:
        """Generate Bear case review for the thesis"""
        bear_review = ReviewCard(
            review_id=str(uuid4()),
            thesis_id=thesis.thesis_id,
            position=ReviewPosition.BEAR,
            summary=f"Bear case against {thesis.target_name} based on {thesis.event_summary}",
            evidence_refs=[e for e in evidence_list if e.confidence_in_evidence > 0.5],
            confidence_score=self._calculate_bear_confidence(thesis, evidence_list),
            reasoning_chain=self._generate_bear_reasoning(thesis, evidence_list),
            invalidation_triggers=self._extract_invalidation_triggers(thesis, ReviewPosition.BEAR),
            created_at=datetime.utcnow().isoformat(),
        )
        logger.debug(
            f"Generated bear review: {bear_review.review_id} for thesis {thesis.thesis_id}"
        )
        return bear_review

    def generate_skeptic_review(
        self,
        thesis: ThesisCard,
        evidence_list: List[EvidenceReference],
        bull_review: ReviewCard,
        bear_review: ReviewCard,
    ) -> ReviewCard:
        """Generate Skeptic review questioning both sides and highlighting methodological issues"""
        skeptic_review = ReviewCard(
            review_id=str(uuid4()),
            thesis_id=thesis.thesis_id,
            position=ReviewPosition.SKEPTIC,
            summary=f"Skeptic review of {thesis.target_name} thesis questioning both bull and bear cases",
            evidence_refs=[e for e in evidence_list if e.confidence_in_evidence > 0.5],
            confidence_score=self._calculate_skeptic_confidence(bull_review, bear_review),
            reasoning_chain=self._generate_skeptic_reasoning(thesis, bull_review, bear_review),
            invalidation_triggers=self._extract_skeptic_invalidation_triggers(
                bull_review, bear_review
            ),
            created_at=datetime.utcnow().isoformat(),
        )
        logger.debug(
            f"Generated skeptic review: {skeptic_review.review_id} for thesis {thesis.thesis_id}"
        )
        return skeptic_review

    def create_cognitive_blackboard(
        self,
        thesis: ThesisCard,
        bull_review: Optional[ReviewCard] = None,
        bear_review: Optional[ReviewCard] = None,
        skeptic_review: Optional[ReviewCard] = None,
    ) -> CognitiveBlackboard:
        """Create a cognitive blackboard aggregating all reviews and evidence"""
        all_evidence: List[EvidenceReference] = []
        conflicting_count = 0

        if bull_review:
            all_evidence.extend(bull_review.evidence_refs)
        if bear_review:
            all_evidence.extend(bear_review.evidence_refs)
            # Check if there's conflicting evidence
            if bull_review:
                bull_evidence_ids = {e.evidence_id for e in bull_review.evidence_refs}
                bear_evidence_ids = {e.evidence_id for e in bear_review.evidence_refs}
                conflicting_count = len(bull_evidence_ids.symmetric_difference(bear_evidence_ids))

        missing_evidence = 0
        if not bull_review or len(bull_review.evidence_refs) == 0:
            missing_evidence += 1
        if not bear_review or len(bear_review.evidence_refs) == 0:
            missing_evidence += 1
        if not skeptic_review or len(skeptic_review.evidence_refs) == 0:
            missing_evidence += 1

        return CognitiveBlackboard(
            blackboard_id=str(uuid4()),
            thesis_id=thesis.thesis_id,
            bull_review=bull_review,
            bear_review=bear_review,
            skeptic_review=skeptic_review,
            aggregated_evidence=all_evidence,
            conflicting_evidence_count=conflicting_count,
            missing_evidence_count=missing_evidence,
        )

    def detect_conflicts(self, blackboard: CognitiveBlackboard) -> ConflictDetectionSummary:
        """Detect conflicts between reviews and check if hard rules are satisfied"""
        conflicting_claims = []
        unresolved_conflicts = 0
        can_promote = True
        has_sufficient_opposing = False
        reasoning = []

        # Hard rule 1: No evidence → cannot enter candidate stage
        if len(blackboard.aggregated_evidence) == 0:
            can_promote = False
            reasoning.append("Failed hard rule: No evidence provided, cannot enter candidate stage")

        # Hard rule 2: No bear/skeptic review → cannot enter validation stage
        if blackboard.bear_review is None or blackboard.skeptic_review is None:
            can_promote = False
            missing = []
            if blackboard.bear_review is None:
                missing.append("Bear")
            if blackboard.skeptic_review is None:
                missing.append("Skeptic")
            reasoning.append(
                f"Failed hard rule: Missing {', '.join(missing)} review, cannot enter validation stage"
            )
        else:
            has_sufficient_opposing = True
            # Check that both bear and skeptic have evidence
            if len(blackboard.bear_review.evidence_refs) == 0:
                can_promote = False
                reasoning.append("Failed hard rule: Bear review has no evidence")
            if len(blackboard.skeptic_review.evidence_refs) == 0:
                can_promote = False
                reasoning.append("Failed hard rule: Skeptic review has no evidence")

        # Find conflicting claims between bull and bear
        if blackboard.bull_review and blackboard.bear_review:
            bull_conclusion = blackboard.bull_review.summary
            bear_conclusion = blackboard.bear_review.summary
            conflicting_claims.append(
                {
                    "bull_claim": bull_conclusion,
                    "bear_claim": bear_conclusion,
                    "evidence_point": "Core thesis direction conflict",
                }
            )
            unresolved_conflicts += 1

        summary = ConflictDetectionSummary(
            conflict_id=str(uuid4()),
            thesis_id=blackboard.thesis_id,
            total_conflicts=len(conflicting_claims),
            conflicting_claims=conflicting_claims,
            unresolved_conflicts=unresolved_conflicts,
            has_sufficient_opposing_view=has_sufficient_opposing,
            can_promote_to_candidate=can_promote,
            reasoning="\n".join(reasoning) if reasoning else "All hard rules satisfied",
        )

        logger.info(
            f"Conflict detection done for thesis {blackboard.thesis_id}: can_promote={can_promote}"
        )
        return summary

    def generate_full_review(
        self,
        thesis: ThesisCard,
        available_evidence: List[EvidenceReference],
    ) -> Dict[str, Any]:
        """Generate full three-position review with conflict detection"""
        # Split evidence by position
        bull_evidence = [
            e
            for e in available_evidence
            if e.description.lower().startswith("bull") or "bull" in e.description.lower()
        ]
        bear_evidence = [
            e
            for e in available_evidence
            if e.description.lower().startswith("bear") or "bear" in e.description.lower()
        ]
        other_evidence = [
            e for e in available_evidence if e not in bull_evidence and e not in bear_evidence
        ]

        # Add other evidence to all (they can use it)
        for e in other_evidence:
            bull_evidence.append(e)
            bear_evidence.append(e)
        skeptic_evidence = available_evidence.copy()

        # Generate all three reviews
        bull = self.generate_bull_review(thesis, bull_evidence)
        bear = self.generate_bear_review(thesis, bear_evidence)
        skeptic = self.generate_skeptic_review(thesis, skeptic_evidence, bull, bear)

        # Create blackboard and detect conflicts
        blackboard = self.create_cognitive_blackboard(thesis, bull, bear, skeptic)
        conflict_summary = self.detect_conflicts(blackboard)

        return {
            "thesis_id": thesis.thesis_id,
            "bull_review": bull,
            "bear_review": bear,
            "skeptic_review": skeptic,
            "cognitive_blackboard": blackboard,
            "conflict_summary": conflict_summary,
        }

    def _calculate_bull_confidence(
        self, thesis: ThesisCard, evidence: List[EvidenceReference]
    ) -> float:
        """Calculate bull confidence based on average evidence confidence"""
        if not evidence:
            return 0.0
        total = sum(e.confidence_in_evidence for e in evidence)
        avg = total / len(evidence)
        if thesis.impact_direction == "positive":
            avg *= 1.1
        return min(avg, 1.0)

    def _calculate_bear_confidence(
        self, thesis: ThesisCard, evidence: List[EvidenceReference]
    ) -> float:
        """Calculate bear confidence based on average evidence confidence"""
        if not evidence:
            return 0.0
        total = sum(e.confidence_in_evidence for e in evidence)
        avg = total / len(evidence)
        if thesis.impact_direction == "negative":
            avg *= 1.1
        return min(avg, 1.0)

    def _calculate_skeptic_confidence(self, bull: ReviewCard, bear: ReviewCard) -> float:
        """Skeptic confidence is based on how much bull and bear disagree"""
        diff = abs(bull.confidence_score - bear.confidence_score)
        # Higher disagreement → higher skeptic confidence that the issue is uncertain
        confidence = 0.5 + (diff / 2)
        return min(confidence, 1.0)

    def _generate_bull_reasoning(
        self, thesis: ThesisCard, evidence: List[EvidenceReference]
    ) -> List[str]:
        """Generate bull reasoning chain from thesis and evidence"""
        reasoning = [
            f"Core thesis: {thesis.event_summary}",
            f"Target asset {thesis.target_name} should benefit from this event",
        ]
        for i, e in enumerate(evidence[:5]):  # Limit to 5 evidence points in reasoning
            reasoning.append(
                f"Evidence {i+1}: {e.description} (confidence: {e.confidence_in_evidence:.2f})"
            )
        reasoning.append(
            f"Overall conclusion: The case is strong with confidence {self._calculate_bull_confidence(thesis, evidence):.2f}"
        )
        return reasoning

    def _generate_bear_reasoning(
        self, thesis: ThesisCard, evidence: List[EvidenceReference]
    ) -> List[str]:
        """Generate bear reasoning chain from thesis and evidence"""
        reasoning = [
            f"Core counter-thesis: {thesis.event_summary} is overrated for {thesis.target_name}",
            f"Downside risks are underappreciated for {thesis.target_name}",
        ]
        for i, e in enumerate(evidence[:5]):
            reasoning.append(
                f"Evidence {i+1}: {e.description} (confidence: {e.confidence_in_evidence:.2f})"
            )
        reasoning.append(
            f"Overall conclusion: The bear case has confidence {self._calculate_bear_confidence(thesis, evidence):.2f}"
        )
        return reasoning

    def _generate_skeptic_reasoning(
        self,
        thesis: ThesisCard,
        bull: ReviewCard,
        bear: ReviewCard,
    ) -> List[str]:
        """Generate skeptic reasoning questioning both sides"""
        reasoning = [
            f"Both bull and bear cases make assumptions that need scrutiny for {thesis.target_name}",
            f"Bull confidence: {bull.confidence_score:.2f}, Bear confidence: {bear.confidence_score:.2f}",
        ]
        if abs(bull.confidence_score - bear.confidence_score) > 0.3:
            reasoning.append("Large disagreement between sides indicates high uncertainty")
        if len(bull.evidence_refs) == 0 or len(bear.evidence_refs) == 0:
            reasoning.append("Key evidence is missing from one or both sides")
        reasoning.append(
            f"Overall skeptic confidence: {self._calculate_skeptic_confidence(bull, bear):.2f}"
        )
        return reasoning

    def _extract_invalidation_triggers(
        self, thesis: ThesisCard, position: ReviewPosition
    ) -> List[str]:
        """Extract invalidation triggers from thesis based on position"""
        if position == ReviewPosition.BULL:
            return [
                *thesis.invalidation_conditions,
                "If the event fails to materialize as expected",
                "If key supporting evidence is disproven",
            ]
        elif position == ReviewPosition.BEAR:
            return [
                "If the event has stronger impact than expected",
                "If contradicting evidence emerges",
                "If the market does not price in the downside",
            ]
        else:
            return []

    def _extract_skeptic_invalidation_triggers(
        self, bull: ReviewCard, bear: ReviewCard
    ) -> List[str]:
        """Extract invalidation triggers for skeptic review"""
        return [
            "If bull and bear reach consensus with high confidence on the same conclusion",
            "If new evidence resolves all key conflicts",
            "If methodological flaws in both sides are addressed",
        ]
