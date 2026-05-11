# Git 分支工作流设置报告

**任务 ID**: af-auto-001-00  
**日期**: 2026-05-11  
**状态**: 完成

## 概述

为 AF-AUTO-001 及后续任务设置了 Git 分支工作流，确保所有实现工作都在特征分支上进行，并通过 Pull Request 合并到 master。

## 修改内容

### 1. CLAUDE.md - 分支工作流规则

在 CLAUDE.md 中新增了"分支工作流规则"章节，规定：

- 不在 master/main 上直接执行 AF-AUTO-001 或后续任务
- 执行实现任务前必须创建或切换到任务分支
- 分支命名约定：`af-auto-001-<简短描述>`
- 每个任务产生一个原子提交或一小系列相关提交
- 任务完成后推送分支并打开 Pull Request
- master/main 仅通过 PR 合并接收更改
- 除非用户明确指示，否则不自动合并 PR
- 仅审计任务（AF-AUTO-000）可以直接提交到 master

### 2. task_af_auto_001.json - 新增任务和依赖

- 新增 `af-auto-001-00` 任务作为第一个任务
- 更新 `af-auto-001-bootstrap` 的依赖为 `af-auto-001-00`
- 更新 `af-auto-001-01a` 的依赖为 `af-auto-001-00`
- 更新 `af-auto-001-03` 的依赖为 `af-auto-001-00`

### 3. run-automation.sh - 分支验证功能

在脚本中新增了以下功能：

- `is_master_branch()`: 检查当前分支是否为 master/main
- `is_audit_task()`: 检查任务是否为审计任务（af-auto-000）
- `validate_branch()`: 在执行任务前验证分支
- 在 `orchestrate_task()` 和 `execute_task()` 中调用分支验证

如果尝试在 master 上执行非审计任务，脚本会：
- 显示错误信息
- 提示如何创建特征分支
- 提供分支命名示例
- 以退出码 5 终止

## 分支命名示例

```
af-auto-001-fix-failing-tests
af-auto-001-reasoning-todos
af-auto-001-quick-win-tests
```

## 推荐工作流程

1. 从最新的 master 创建分支
   ```bash
   git checkout master
   git pull
   git checkout -b af-auto-001-<task-description>
   ```

2. 执行任务
   ```bash
   .ai/scripts/run-automation.sh execute af-auto-001-xx --yes
   ```

3. 推送分支并创建 PR
   ```bash
   git push -u origin af-auto-001-<task-description>
   # 然后在 GitHub 上创建 PR
   ```

## 验证

已在当前分支 `af-auto-001-setup-branch-workflow` 上验证分支检查功能正常工作。

## 下一步

此任务完成后，`af-auto-001-01a` 和 `af-auto-001-03` 任务现在可以开始执行（都依赖于 `af-auto-001-00`）。
