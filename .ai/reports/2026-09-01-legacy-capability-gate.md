# LSH 兼容适配与删除门禁实施报告

## 范围

- 新增版本化 LSH capability 清单与 fail-closed 删除门禁。
- 把现有首页、资产、主题和研究工作台的数据调用切向合并平台领域 API，不调整视觉设计。
- 明确保留策略、交易和基金审批为只读冻结能力。

## 已实现

- 删除候选必须同时具备 data migration、parity、regression、zero-call、archive path、stable-version observation 和 archived lifecycle 证据。
- 未知或格式错误的清单拒绝加载；未知 capability 拒绝评估。
- 首页不生成 AI 点评；资产事实读取不自动启动 Agent；研究消息只写研究区。

## 验证证据

- `python -m pytest tests/unit/test_legacy_capability_gate.py tests/unit/test_merged_platform_frontend_contract.py tests/unit/test_research_workbench_frontend.py -q`：10 passed。
- `node --check`：dashboard、asset、industry、research-workbench 四个模块通过语法检查。

## 未验证与门禁

- 清单中的迁移、parity、连续零调用、只读归档和稳定版本观察目前均未形成生产证据，故没有执行 LSH 停止或删除。
- 未执行原生 Windows CI 或真实 Windows 安装级冒烟；桌面发布仍受该门禁约束。
