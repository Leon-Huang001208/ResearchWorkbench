# Wind 清理未确认恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development with independent specification and quality reviews.

**Goal:** 为清理失败保留明确活动见证，并提供不把未知冒充空闲的同版本恢复合同。

**Architecture:** 沿既有 Host、Native manager、resident admission 和 BirthFence；普通 active/部署拒绝门保持。维护只接受本版本真实、完整、独立见证：Wind 清理未确认且全部 Future 已结束，其他每项无活动，无 Native 研究。旧 Host 没有见证时必须拒绝；不注入、不把日志补成见证，也不声称可自动修复当前旧进程。

**Tech Stack:** 既有 Python、FastAPI、系统进程与文件锁；无新依赖。

## 本轮安全闭包与未实现部分

原常驻 supervisor 使用不可变 `controller.pyz`；仅改新源码的 controller guard 不能阻止旧 artifact 自动恢复，也不能发布错误格式的旧 transaction 冒充新 journal。因此先交付逐项见证、严格只读维护 preflight 和有界、无信号升级的私有停止 primitive，不开放 apply。该闭包用于补齐真实证据与安全构件，不宣称完整恢复通道完成；下面的事务、控制器版本迁移及现场恢复仍未实现。后继必须先解决不可变控制器的受控升级和崩溃恢复契约，不能靠一般 allow_unknown 或伪造旧日志绕过。

## 已确定现场

- 原始失败由真实 `verify_primary` 返回 `research_active_or_unknown`；Host active=null，Native active count=0。
- Wind poison 使 SDK 见证抛错。普通 stop 等待十秒后可能 SIGKILL；关闭钩子会取消工作，不能当无副作用操作。
- 用户允许下一步修复；新版本实际部署仍须具体可审版本授权。Excel/Wind、全部工作簿、旧 Run/输入、账户/模型/会话保护；定时禁用；不重发模型。

## 实施顺序

- [x] 先新增失败测试，覆盖 poison 与 Future 运行/结束/其他未知混合，以及旧 Host 缺见证。
- [x] Host 公开固定、无秘密的分项见证；保留原活动门并加强晚到未知/忙状态的拒绝；检查不得短路。
- [x] 实现只读维护 preflight。所有身份、见证、Native/全账号/市场/后台空闲、版本/安装/端口、原有 journal 和恢复状态必须完整；不能接受调用者自填见证；结果明确不可执行维护。
- [ ] 后继：封闭同版本恢复事务和不可变控制器的受控兼容迁移，未完成前不开放 apply。
- [ ] 保留三锁、BirthFence、全账号保全、持久可恢复 journal；只对精确 owned PID 发送一次单 PID SIGTERM，绝不升级信号或调用带强杀后备的旧 stop/restart/rollback。
- [ ] 停机超时/未知/保全失败保持 journal/fence，不自动启动、回滚或重放。恢复由显式同一事务继续，已发送信号不得重发；全部旧 PID 退休、端口空闲且保全一致后才同版启动。
- [ ] 未完成 journal 阻断普通 supervisor/start/部署绕入；成功释放前原普通 Primary/Host/Native/后台门须重新明确通过。
- [ ] 如果现有复用接口无法保持这些条件，先报告具体合同缺口，不能加入宽泛 allow_unknown、伪造 idle 或偷偷减少原门。
- [ ] 相邻回归、独立规格/质量评审、完整 Router、通用 CI 和同候选 Mac 安装，按受管交付发布 PR。

## 验收与限制

源码/CI 与旧实例现场恢复分开。旧 b800 缺分项见证，任何本轮新操作员必须明确拒绝，不能仅因用户允许同版重启就认证旧清理已完成。现场历史稿、Word、认证下载和三周稳定性继续保留未完成；本计划不授权新供应商/模型重试、日程、依赖或破坏性清理。
