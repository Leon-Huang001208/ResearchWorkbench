"""Unit tests for the Bull/Bear/Skeptic review framework"""
from datetime import datetime

from core.contracts import (
    CognitiveBlackboard,
    EvidenceReference,
    PropagationPath,
    ReviewCard,
    ReviewPosition,
    ThesisCard,
)
from core.services.thesis_review_service import ThesisReviewService


def test_create_evidence_reference():
    """Test that EvidenceReference model works correctly"""
    evidence = EvidenceReference(
        evidence_id="test-ev-1",
        evidence_type="event",
        url="https://example.com/evidence/1",
        description="Test event showing increasing demand",
        confidence_in_evidence=0.8,
    )
    assert evidence.evidence_id == "test-ev-1"
    assert evidence.confidence_in_evidence == 0.8
    assert evidence.url is not None


def test_create_review_card():
    """Test that ReviewCard model works correctly"""
    evidence = EvidenceReference(
        evidence_id="test-ev-1",
        evidence_type="event",
        description="Test event",
        confidence_in_evidence=0.8,
    )
    review = ReviewCard(
        review_id="test-r-1",
        thesis_id="test-t-1",
        position=ReviewPosition.BULL,
        summary="Bull case test",
        evidence_refs=[evidence],
        confidence_score=0.75,
        reasoning_chain=["Point 1", "Point 2"],
        invalidation_triggers=["If X happens"],
        created_at=datetime.utcnow().isoformat(),
    )
    assert review.position == ReviewPosition.BULL
    assert len(review.evidence_refs) == 1
    assert review.confidence_score == 0.75


def test_cognitive_blackboard_creation():
    """Test cognitive blackboard creation aggregates evidence correctly"""
    service = ThesisReviewService()
    thesis = create_test_thesis()

    bull_evidence = [
        EvidenceReference(
            evidence_id="bull-1",
            evidence_type="event",
            description="Bull evidence 1",
            confidence_in_evidence=0.8,
        ),
        EvidenceReference(
            evidence_id="common-1",
            evidence_type="data",
            description="Common evidence",
            confidence_in_evidence=0.7,
        ),
    ]
    bear_evidence = [
        EvidenceReference(
            evidence_id="bear-1",
            evidence_type="event",
            description="Bear evidence 1",
            confidence_in_evidence=0.75,
        ),
        EvidenceReference(
            evidence_id="common-1",
            evidence_type="data",
            description="Common evidence",
            confidence_in_evidence=0.7,
        ),
    ]

    bull = service.generate_bull_review(thesis, bull_evidence)
    bear = service.generate_bear_review(thesis, bear_evidence)

    blackboard = service.create_cognitive_blackboard(thesis, bull, bear)

    # Common evidence should be in aggregated twice (once from each)
    assert len(blackboard.aggregated_evidence) == 4
    # One unique conflict between bull and bear
    assert blackboard.conflicting_evidence_count == 2
    assert blackboard.missing_evidence_count == 1  # Skeptic missing


def test_hard_rule_no_evidence_cannot_promote():
    """Test hard rule: No evidence → cannot promote"""
    service = ThesisReviewService()
    thesis = create_test_thesis()

    blackboard = CognitiveBlackboard(
        blackboard_id="test-bb-1",
        thesis_id=thesis.thesis_id,
        aggregated_evidence=[],
    )

    summary = service.detect_conflicts(blackboard)
    assert summary.can_promote_to_candidate is False
    assert "No evidence provided" in summary.reasoning


def test_hard_rule_missing_bear_cannot_promote():
    """Test hard rule: Missing bear/skeptic review → cannot promote"""
    service = ThesisReviewService()
    thesis = create_test_thesis()

    evidence = [
        EvidenceReference(
            evidence_id="test-1",
            evidence_type="event",
            description="Test",
            confidence_in_evidence=0.8,
        ),
    ]

    bull = service.generate_bull_review(thesis, evidence)
    blackboard = service.create_cognitive_blackboard(thesis, bull_review=bull)

    summary = service.detect_conflicts(blackboard)
    assert summary.can_promote_to_candidate is False
    assert summary.has_sufficient_opposing_view is False
    assert "Missing Bear" in summary.reasoning


def test_full_valid_review_can_promote():
    """Test a full valid review passes all hard rules"""
    service = ThesisReviewService()
    thesis = create_test_thesis()

    evidence = [
        EvidenceReference(
            evidence_id="bull-1",
            evidence_type="event",
            description="Bull: Q3 earnings beat",
            confidence_in_evidence=0.9,
        ),
        EvidenceReference(
            evidence_id="bear-1",
            evidence_type="event",
            description="Bear: Competition increasing",
            confidence_in_evidence=0.8,
        ),
        EvidenceReference(
            evidence_id="macro-1",
            evidence_type="data",
            description="Skeptic: Interest rates rising",
            confidence_in_evidence=0.75,
        ),
    ]

    result = service.generate_full_review(thesis, evidence)
    assert "bull_review" in result
    assert "bear_review" in result
    assert "skeptic_review" in result
    assert "conflict_summary" in result

    conflict_summary = result["conflict_summary"]
    assert conflict_summary.can_promote_to_candidate is True
    assert conflict_summary.has_sufficient_opposing_view is True


def test_conflict_detection_finds_conflict():
    """Test conflict detection identifies conflict between bull and bear"""
    service = ThesisReviewService()
    thesis = create_test_thesis()

    evidence = [
        EvidenceReference(
            evidence_id="bull-1",
            evidence_type="event",
            description="Bull evidence",
            confidence_in_evidence=0.8,
        ),
        EvidenceReference(
            evidence_id="bear-1",
            evidence_type="event",
            description="Bear evidence",
            confidence_in_evidence=0.8,
        ),
    ]

    result = service.generate_full_review(thesis, evidence)
    assert result["conflict_summary"].total_conflicts == 1


def create_test_thesis() -> ThesisCard:
    """Helper to create a test thesis card"""
    return ThesisCard(
        thesis_id="test-thesis-001",
        event_summary="NVDA releases new AI chip with higher margins",
        propagation_path=PropagationPath(),
        target_symbol="NVDA",
        target_name="NVIDIA Corporation",
        mapping_reason="Direct revenue impact",
        supporting_evidence=["ev-001"],
        contradicting_evidence=[],
        invalidation_conditions=["Chip launch delayed"],
        overall_confidence=0.7,
        impact_direction="positive",
        created_at=datetime.utcnow().isoformat(),
    )
