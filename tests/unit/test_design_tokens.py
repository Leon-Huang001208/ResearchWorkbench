"""Phase 4 测试 — DesignTokens 扩展字段（ppt_template_path, ppt_transition）."""

import pytest

from core.contracts.document import (
    DesignTokens,
    brief_tokens,
    presentation_tokens,
    report_tokens,
)


class TestDesignTokensPPTFields:
    """PPT 扩展字段测试."""

    def test_default_ppt_template_path_is_none(self):
        """默认无 PPT 模板路径."""
        tokens = DesignTokens()
        assert tokens.ppt_template_path is None

    def test_default_ppt_transition_is_none(self):
        """默认无 PPT 过渡效果."""
        tokens = DesignTokens()
        assert tokens.ppt_transition is None

    def test_set_ppt_template_path(self):
        """可设置 PPT 模板路径."""
        tokens = DesignTokens(ppt_template_path="templates/custom.pptx")
        assert tokens.ppt_template_path == "templates/custom.pptx"

    def test_set_ppt_transition(self):
        """可设置 PPT 过渡效果."""
        tokens = DesignTokens(ppt_transition="fade")
        assert tokens.ppt_transition == "fade"

    def test_ppt_transition_none_value(self):
        """ppt_transition 为 "none" 表示无过渡."""
        tokens = DesignTokens(ppt_transition="none")
        assert tokens.ppt_transition == "none"

    def test_ppt_transition_push(self):
        """push 过渡效果."""
        tokens = DesignTokens(ppt_transition="push")
        assert tokens.ppt_transition == "push"

    def test_ppt_transition_cut(self):
        """cut 过渡效果."""
        tokens = DesignTokens(ppt_transition="cut")
        assert tokens.ppt_transition == "cut"


class TestDesignTokensPresets:
    """预设令牌测试."""

    def test_report_tokens_have_ppt_fields(self):
        """研报预设令牌应有 PPT 扩展字段."""
        tokens = report_tokens()
        assert hasattr(tokens, "ppt_template_path")
        assert hasattr(tokens, "ppt_transition")

    def test_presentation_tokens_have_ppt_fields(self):
        """演示文稿预设令牌应有 PPT 扩展字段."""
        tokens = presentation_tokens()
        assert hasattr(tokens, "ppt_template_path")
        assert hasattr(tokens, "ppt_transition")

    def test_brief_tokens_have_ppt_fields(self):
        """简报预设令牌应有 PPT 扩展字段."""
        tokens = brief_tokens()
        assert hasattr(tokens, "ppt_template_path")
        assert hasattr(tokens, "ppt_transition")

    def test_presentation_tokens_have_custom_heading_sizes(self):
        """演示文稿令牌应有更大的标题字号."""
        tokens = presentation_tokens()
        assert tokens.heading_sizes[1] == 36
        assert tokens.body_size == 14


class TestDesignTokensSerialization:
    """序列化/反序列化测试."""

    def test_ppt_fields_roundtrip(self):
        """PPT 扩展字段序列化往返."""
        tokens = DesignTokens(
            ppt_template_path="path/to/template.pptx",
            ppt_transition="fade",
        )
        d = tokens.model_dump()
        restored = DesignTokens(**d)
        assert restored.ppt_template_path == "path/to/template.pptx"
        assert restored.ppt_transition == "fade"

    def test_ppt_fields_partial(self):
        """部分 PPT 字段反序列化."""
        tokens = DesignTokens(ppt_transition="push")
        d = tokens.model_dump()
        restored = DesignTokens(**d)
        assert restored.ppt_template_path is None
        assert restored.ppt_transition == "push"

    def test_ppt_fields_json_schema(self):
        """JSON schema 应包含 PPT 字段."""
        schema = DesignTokens.model_json_schema()
        assert "ppt_template_path" in schema["properties"]
        assert "ppt_transition" in schema["properties"]
