# 长期研究档案后端实施回执

宿主：macOS；任务：Web功能开发。范围：阶段1后端、近处Host／原DSH接线、受管MCP只读鉴权边界及Python／JS离线回归。未安装新依赖，未连接正式数据库、真实模型或供应商，未处理真实供应商凭据、未部署。

## 变更

- 新增个人SQLite元数据、账户根／schema身份、不可变记录事件、版本投影、并发修订及幂等原响应。GET不创建档案文件，回执只保留版本指针，原件不复制。
- 证据与保全pin同事务提交；共享非阻塞保全锁覆盖原生session.delete至Host purge。源字节／权限变化明确失败，软删保留原件。
- 来源、dataset及受控文件逐次Host解析／鉴权。数据观察期不冒充公开时间；原生MCP及档案MCP原件保持clue并重验受管grant，普通数据集文件／复制入口不能绕读。
- 草稿生成不调用模型。用户实际发送Prompt时才消费不透明handoff_id，绑定单一sid与已有资料范围；普通创建、@候选与文本不授权。原DSH的research_read_source与质量观察识别绑定原件，原报告质量门保持。
- 会话／文件／报告成果关联只信Host，缺失报告原件不能创建报告成果；原quality和hash固定，不保存报告正文。支持登记文件ID或登记的相对路径。
- SQLite一致快照备份／恢复校验账户、数据库、引用pin及原件后原子替换；失败保留旧库。API与非HTTP事务、备份／恢复及绑定均有resident admission。

## 实际验证

使用已经存在且经主代理确认可用的 `/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python`；未安装、修改该环境。

- 最终近处回归：`RESEARCH_MCP_RUNTIME_ENABLED=0 <python> -m pytest tests/research_web/test_dossiers.py tests/research_web/test_dossier_api.py tests/research_web/test_store.py tests/research_web/test_research_source_reading.py --confcutdir=tests/research_web -q`：**52 passed，6.96s**。日志 `/tmp/rwb-dossier-final-local.log`。
- 之前扩大回归另外包含 `test_research_quality_scope.py`、`test_research_calculations.py`、`test_fingpt_dsh_fusion.py`：**116 passed，91.23s**。该次发生在最终Prompt-only绑定修订之前；最终改动已重跑上述52项，不冒充同一次候选运行。日志 `/tmp/rwb-dossier-regression.log`。
- `node --test tests/javascript/research_web_quality_tool.test.mjs`：**16 passed**，包括档案canonical来源身份与精确preflight参数。日志 `/tmp/rwb-dossier-js.log`。
- 最终定点Ruff、Black（17个Python文件）、isort与 `git diff --check` 均通过；未以格式化代替业务验收。

新增场景覆盖真实子进程重开、首次事务失败可重试、证据／pin同回滚、版本并发、cross-root／路径逃逸／符号链接、hash／缺失／撤权、软删dataset、原生删除前置与RPC期间竞态、恢复失败保旧、一receipt跨sid拒绝、Host未通过报告保留及来源别名拒绝。

测试采用隔离临时Store、假DSH传输及内存keyring；测试中初始化账户服务会产生既有业务目录，但没有对常驻用户根执行操作。环境的Starlette／anyio弃用提示仍保留。

## 待整合与未执行

- 本后端依赖同任务MCP构造器的 `evidence_store` 及同步 `assert_frozen_result_authorized`；本分支运行时MCP保持关闭，完整组合必须由主代理合入MCP分支后再验证。
- 全changed-set Router、独立安全／Python／JS评审、GitHub通用检查、同候选macOS干净安装、真实浏览器与常驻验收由主任务统一完成。本回执不宣称CI／发布／部署通过。
- 二进制证据仅显示binary_source，没有新增PDF／Office提取器。手工文件和来源被外部删除／改写不能由保全锁防止；读取显示实际缺口。
- 正式恢复、常驻部署和小创18次收费实测仍不在本次执行范围。Windows／Linux原生验收NOT_RUN。
