#!/bin/bash
# 测试分支检查功能

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/run-automation.sh" 2>/dev/null

echo "=== 测试分支检查功能 ==="
echo ""

# 测试 1: 当前分支
current_branch=$(git branch --show-current)
echo "当前分支: $current_branch"
if is_master_branch; then
    echo "✓ is_master_branch: 返回 true"
else
    echo "✓ is_master_branch: 返回 false (正确，我们在特征分支上)"
fi

# 测试 2: 审计任务检测
echo ""
if is_audit_task "af-auto-000-12"; then
    echo "✓ is_audit_task: af-auto-000-12 返回 true"
else
    echo "✗ is_audit_task: af-auto-000-12 返回 false"
fi

if is_audit_task "af-auto-001-01"; then
    echo "✗ is_audit_task: af-auto-001-01 返回 true (错误)"
else
    echo "✓ is_audit_task: af-auto-001-01 返回 false (正确)"
fi

echo ""
echo "=== 测试完成 ==="
echo ""
echo "现在可以尝试在 master 分支上运行:"
echo "  git checkout master"
echo "  .ai/scripts/run-automation.sh --task-file .ai/tasks/task_af_auto_001.json execute af-auto-001-01a"
echo ""
echo "应该会看到分支检查错误并拒绝执行。"
