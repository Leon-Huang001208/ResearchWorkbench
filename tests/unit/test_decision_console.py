"""分析师循环决策控制台测试。

测试覆盖：
- 决策工作区创建、关闭、添加候选
- 决策动作记录（approve/reject/watch/defer等）
- 审计追踪记录
- 复盘记录创建和查询
- 决策-结果关联
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock

from core.contracts.decision_console import (
    AnalystDecision,
    DecisionAction,
    DecisionWorkspace,
    PostMortemRecord,
)
from core.services.decision_console_service import DecisionConsoleService
from data_layer.repositories.decision_console_repository import DecisionConsoleRepository


# ─── 测试设置 ────────────────────────────────────────────

def mock_db_session():
    """创建模拟DB session"""
    return MagicMock()


def get_test_service():
    """获取测试服务实例"""
    db = mock_db_session()
    repo = DecisionConsoleRepository(db)
    return DecisionConsoleService(repository=repo)


# ─── Workspace 测试 ─────────────────────────────────────

class TestWorkspaceManagement:
    """测试工作区管理"""

    def test_create_workspace(self):
        """测试创建工作区"""
        service = get_test_service()
        saved = []

        # 捕获保存并返回我们自己的对象
        def capture_save(workspace):
            saved.append(workspace)
            return workspace

        service.repo.save_workspace = capture_save

        workspace = service.create_workspace(
            created_by="test-analyst",
            candidate_ids=["candidate-001", "candidate-002"]
        )

        assert workspace.workspace_id is not None
        assert workspace.created_by == "test-analyst"
        assert len(workspace.candidate_ids) == 2
        assert workspace.status == "open"

    def test_close_workspace(self):
        """测试关闭工作区"""
        service = get_test_service()

        # 模拟已有工作区
        existing = DecisionWorkspace(
            workspace_id="ws-001",
            workspace_date=datetime.now(UTC),
            created_by="test-analyst",
            status="open",
        )

        # 模拟repo get
        service.repo.get_workspace = MagicMock(return_value=existing)

        # 捕获保存
        saved = []
        def capture_save(workspace):
            saved.append(workspace)
            return workspace
        service.repo.save_workspace = capture_save

        closed = service.close_workspace("ws-001", notes="Daily review done")
        assert closed is not None
        assert closed.status == "closed"
        assert closed.closed_at is not None
        assert closed.notes == "Daily review done"

    def test_add_candidates_to_workspace(self):
        """测试添加候选到工作区"""
        service = get_test_service()

        existing = DecisionWorkspace(
            workspace_id="ws-001",
            workspace_date=datetime.now(UTC),
            created_by="test-analyst",
            candidate_ids=["candidate-001"],
        )
        service.repo.get_workspace = MagicMock(return_value=existing)

        # 捕获保存
        saved = []
        def capture_save(workspace):
            saved.append(workspace)
            return workspace
        service.repo.save_workspace = capture_save

        updated = service.add_candidates_to_workspace("ws-001", ["candidate-002", "candidate-003"])

        assert len(updated.candidate_ids) == 3
        assert "candidate-002" in updated.candidate_ids
        assert "candidate-003" in updated.candidate_ids


# ─── Decision Action 测试 ───────────────────────────────

class TestDecisionActions:
    """测试决策动作记录"""

    def test_record_new_approve_decision(self):
        """测试记录新的批准决策"""
        service = get_test_service()

        service.repo.get_decision_by_candidate = MagicMock(return_value=None)

        saved_decision = []
        def capture_save_decision(decision):
            saved_decision.append(decision)
            return decision
        service.repo.save_decision = capture_save_decision

        saved_audit = []
        def capture_save_audit(audit):
            saved_audit.append(audit)
            return audit
        service.repo.save_audit = capture_save_audit

        action = DecisionAction(
            action_type="approve",
            action_by="analyst-001",
            rationale="This signal has strong historical evidence and good risk-reward",
        )

        decision, audit = service.record_decision(
            workspace_id="ws-001",
            candidate_id="signal-001",
            candidate_type="signal",
            previous_status="candidate",
            action=action,
        )

        assert decision.decision_id is not None
        assert decision.workspace_id == "ws-001"
        assert decision.candidate_id == "signal-001"
        assert decision.final_action.action_type == "approve"
        assert decision.final_action.action_by == "analyst-001"
        assert len(decision.revision_history) == 0
        assert audit is not None
        assert audit.action == "approve"

    def test_record_revision_decision(self):
        """测试记录修订决策（已有历史）"""
        service = get_test_service()

        # 已有决策
        existing = AnalystDecision(
            decision_id="decision-001",
            workspace_id="ws-001",
            candidate_id="signal-001",
            candidate_type="signal",
            previous_status="candidate",
            final_action=DecisionAction(
                action_type="watch",
                action_by="analyst-001",
                rationale="Need more evidence",
            ),
        )

        service.repo.get_decision_by_candidate = MagicMock(return_value=existing)

        saved_decision = []
        def capture_save_decision(decision):
            saved_decision.append(decision)
            return decision
        service.repo.save_decision = capture_save_decision

        saved_audit = []
        def capture_save_audit(audit):
            saved_audit.append(audit)
            return audit
        service.repo.save_audit = capture_save_audit

        new_action = DecisionAction(
            action_type="approve",
            action_by="analyst-001",
            rationale="Got additional evidence, now approve",
        )

        decision, audit = service.record_decision(
            workspace_id="ws-001",
            candidate_id="signal-001",
            candidate_type="signal",
            previous_status="watch",
            action=new_action,
        )

        assert decision.decision_id == "decision-001"  # 保留原ID
        assert len(decision.revision_history) == 1
        assert decision.revision_history[0].action_type == "watch"
        assert decision.final_action.action_type == "approve"
        assert audit is not None
        assert len(audit.before_state) > 0  # 保存了之前状态


# ─── Post-Mortem 测试 ───────────────────────────────────

class TestPostMortem:
    """测试复盘功能"""

    def test_create_post_mortem(self):
        """测试创建复盘记录"""
        service = get_test_service()

        saved = []
        def capture_save(post_mortem):
            saved.append(post_mortem)
            return post_mortem
        service.repo.save_post_mortem = capture_save

        post_mortem = service.create_post_mortem(
            decision_id="decision-001",
            original_decision="approve entry at current price",
            realized_outcome="win",
            learning_points="The signal worked better than expected, should take larger position next time",
            outcome_metrics={"excess_return_pct": 5.2, "holding_days": 12},
            linked_signal_accuracy=0.75,
        )

        assert post_mortem.post_mortem_id is not None
        assert post_mortem.decision_id == "decision-001"
        assert post_mortem.realized_outcome == "win"
        assert "excess_return_pct" in post_mortem.outcome_metrics
        assert post_mortem.linked_signal_accuracy == 0.75
        assert len(post_mortem.learning_points) > 0

    def test_update_post_mortem_outcome(self):
        """测试更新复盘结果"""
        service = get_test_service()

        existing = PostMortemRecord(
            post_mortem_id="pm-001",
            decision_id="decision-001",
            original_decision="approve",
            realized_outcome="pending",
            learning_points="Waiting for outcome",
        )

        service.repo.get_post_mortem = MagicMock(return_value=existing)

        saved = []
        def capture_save(post_mortem):
            saved.append(post_mortem)
            return post_mortem
        service.repo.save_post_mortem = capture_save

        updated = service.update_post_mortem(
            post_mortem_id="pm-001",
            realized_outcome="loss",
            outcome_metrics={"excess_return_pct": -2.1},
            learning_points="The sector rotated faster than expected",
        )

        assert updated is not None
        assert updated.realized_outcome == "loss"
        assert updated.outcome_metrics["excess_return_pct"] == -2.1
        assert updated.updated_at is not None


# ─── Audit 测试 ─────────────────────────────────────────

class TestAuditTrail:
    """测试审计追踪"""

    def test_get_audit_history(self):
        """测试获取审计历史"""
        service = get_test_service()

        service.repo.get_audit_for_decision = MagicMock(return_value=[])

        audits = service.get_audit_history("decision-001")

        assert audits is not None
        assert isinstance(audits, list)
