# Research Workbench 文档治理

## 范围

- 以远端默认分支 `4066c2e637362ca107b50fe63e5cba20fa7d9c36` 为事实基线。
- 收敛现役 README、架构、开发映射、参考、数据源、备份和 Changelog。
- 对全部受跟踪 Markdown 建立状态分类、主题权威、链接和退役命令门禁。
- 历史计划、设计、任务、验收、累计评审和旧平台手册集中归档。
- 原主工作区的未提交覆盖层保持只读，未进入本任务 worktree。

## 文档影响决策

新的治理检查仍位于既有离线 Documentation Gate 边界内：不改变 Research Web 的文档 HTTP 路由、固定 HTML 白名单、CSP、DSH、DataHub 或产品运行拓扑。因此图 08 的节点和关系保持不变；本次更新的是门禁内部的分类与证据来源。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"新增文档分类、权威唯一性、链接、退役命令和生成索引检查，但仍属于既有离线 Documentation Gate，不改变 Research Web 文档服务拓扑。","diagrams":[]} -->

## 验证

- `node scripts/check_documentation_governance.mjs --project .`：473 个当前/新增 Markdown 全部分类，58 个 current 文档完成权威、链接、锚点、退役命令和归档告示检查，`violations: []`。
- `node --test tests/javascript/documentation_governance.test.mjs tests/javascript/research_web_architecture.test.mjs tests/javascript/merged_platform_blueprint.test.mjs`：77 passed。
- `python -m pytest tests/research_web/test_documentation.py tests/research_web/test_doc_sync.py tests/scripts/test_generate_py_file_index.py tests/unit/test_legacy_capability_gate.py --confcutdir=tests/research_web -q`：35 passed，1 个第三方 DeprecationWarning。
- `python scripts/check_doc_sync.py --project . --base origin/master`：治理、生成索引和 Research Web 架构三层均通过。
- `node .agents/project-constraints.mjs` 使用完整 changed-file 集：`violations: []`。
- `ruff`、`black --check`、`isort --check-only`、`git diff --check` 与 Node 语法检查通过。

## 事实面状态

| 事实面 | 状态 | 说明 |
| --- | --- | --- |
| 代码 | changed-and-verified | 仅文档治理脚本、生成器和回归测试变化；产品 API/模型/运行时未改 |
| 运行态 | not-applicable | 本轮不改 Research Web 运行行为，未把服务或浏览器检查写成通过 |
| 文档 | changed-and-verified | 现役入口收敛、历史集中归档、全部 Markdown 纳管 |
| 规则 | changed-and-verified | AGENTS 继续为真身，CLAUDE 与 UI Skill 去重并纠正源码边界 |
| 记忆 | out-of-scope | Codex 生成记忆保持只读；项目过期待办进入历史归档 |
| 工作区 | pending | 用户已确认清场；候选文件进入删除提交，受管 worktree 在第二轮 CI 后清理 |

## 清理结果

- 用户在完整交付汇报后明确授权清理。
- `_temp_buffer.md` 与 `tests/deep-research-report.md` 已进入受管 Git 删除提交，可从历史恢复。
- 原工作区未跟踪的 `_temp_buffer.docx` 在远端删除提交通过后单独移除。
