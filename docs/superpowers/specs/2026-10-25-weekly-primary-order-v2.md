# 华安监控等待维护：真实 Primary 活动门顺序修复

## 现场与目标

b0ebe1df 的首次受管执行在停机、领域写入之前安全返回 research_or_maintenance_busy。四个升级/监控 journal、intent、receipt 均不存在；生产仍为36fd，旧unknown、会话、数据、模型未改变。现场明确：LegacyBinding.verify.active=true，Native活动列表为空；operate首处verify_primary进入真实gateway_upgrade.verify_primary，在维护桥之前因Host把旧needs_attention计入active而拒绝。此前集成mock了verify_primary，漏测真实顺序。

目标仅纠正此顺序。保留已经发布v1及所有旧模式的身份、payload、验证与恢复行为；新增reviewed-etf-weekly-admission-v2 / apply-etf-weekly-admission-v2。前版仍固定36fd，封印action及operation不变，最终完整产品祖先须覆盖最新已验证主线。业务数据和唯一DSH、报告质量、历史禁止定稿、定时关闭的边界不变。

## 严格的分阶段验证

1. 只有v2显式paired flags可进入新路径。原三锁、最新源码/CI/controller/目录/旧版/恢复资格保留；不增加全局allow_active或强制执行参数。
2. 首处不能只删除verify_primary。v2先复用真实LegacyBinding.discover.verify，证明原全部非活动身份、目录、owner、配置、版本及服务归属；active必须明确bool，Native探针结果必须明确空列表，Automation索引检查保留。这里active=true只是一项观察，不是空闲证明；未知立即拒绝。
3. 旧模式首处仍调用原完整verify_primary，不改变gateway_upgrade.py或其通用活动条件。
4. 原有桥在三锁和冻结身份/owner/旧协议/源/claim检查后，仅结束已获授权的旧Workflow等待。它不停止任何计算，不取消Native、不重发模型、不改原unknown及数据。
5. 释放catalog锁但持原三锁，旧GET刷新Host之后，v2必须调用真实完整verify_primary，再明确检查新读Host.active为False、Native返回list且为空，接着执行原完整Operations.idle。任何其它活动或未知仍拒绝服务切换；不伪造active、Header、Cookie或空列表。
6. 已授权等待结束后若后续活动门拒绝，保留独立领域回执，代码切换deferred；不自动逆转控制决定。恢复stopped边界保持原纯验证及回滚语义，不强加不可能的live检查，不重做领域动作。

## 回归和交付

- RED须让真实gateway_upgrade.verify_primary参与，证明v1及原顺序在桥前拒绝，不能mock该函数、mock完整idle或只检查调用名称。
- GREEN使用真实LegacyBinding逻辑与受控传输/OS边界，证明v2身份预检→桥→GET→原完整g.verify_primary→严格后检→原idle；原v1保持拒绝。
- 覆盖Host活动在桥后仍存在、Native活动/None/非list、Host非bool、owner/目录/版本/索引问题，保证不能越过最终门或执行停机。新旧模式无flag/错flag、恢复与现有故障矩阵保留。
- 完整本机、邻近历史/quality/admission、Router、独立规格/质量、同候选原三CI和Mac干净安装全部重新绑定。旧b0e的绿不替代新候选。
- 本任务只交付必要修复，不执行常驻apply或模型。独立协调任务在全部资格和live门通过后执行唯一事务；已使用464秒，剩余正式窗口1336秒，不暗重置。230报告和228工具按协调顺序处理，不能静默把新业务纳入payload。

## 通知授权

人类在协调任务直接选择“允许协调，统一部署窗口”，其原问题明确包含与周报、全市场任务的跨任务协调。正式候选完成后，依据这项已核验的人类授权，仅向该协调任务发送一次就绪消息，带精确merged/source/产品/CI和交接引用；不会以另一任务的要求本身代替人类授权，也不授新模型、取消或删除权限。
