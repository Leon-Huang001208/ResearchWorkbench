# 普通用户报告invalid/409修复

宿主macOS Mac mini，功能缺陷修复；本平台本机Native与macOS安装CI验收，Windows/Linux产品验收NOT_RUN。用户明确授权不放宽质量门、保留既有会话模型、部署后再做一次四用户真实模型并发交付与隔离验收。

开始使用opaque Harness会话及受管Git独立worktree；旧3个失败会话仅只读复制到私有离线fixture，原数据不写。实际复现三例均invalid，分别21/13/18个问题，均有file来源身份不符。未读取模型密钥、未启动付费复测。

根因：原生提示没有Host规范来源标题/全文摘要；原数值观察仅CSV前12KB，无法核对全量派生指标；Delivery FINAL无视后续报告输出集合/字节变化，历史归档也可能参与本轮格式判断。保持原assess_quality规则与invalid下载409；只补真实可复算证据、同scope结果和原sandbox重验。

新增data-only buy_and_hold配方严格边界和Host独立Decimal复算；全量字节、来源ID、用户根/session/task/算法/配方SHA绑定；缓存仅64条结果、不缓存原文，每次先核全文SHA。原sources/notes/coverage不自动改写，原补查次数不增加。CPU工作移出事件循环，返回前复查完整scope。

定点回归先红：新计算模块缺失与FINAL旧缓存/历史归档可满足交付均复现。实现后先过15项计算与2项交付；独立评审发现严格CSV、配方顺序和scope边界，新增对应反例。旧安全回归的valid=false、missing_formats和持久化断言保留，不弱化为只看状态；不可读输入明确质量invalid，不使详情接口无结构报错。最终验收、CI与真实模型结果待实际执行记录。

依赖和安装：无新依赖或持久schema；已核requirements/web.in、web.lock、setup_web.py与Bootstrap合同，无需改锁；实际干净安装证据仍待最终候选CI。

本地证据：质量/交付/报告闭包115 passed；新增三个模块35 passed；Router L4的治理、架构、协议与文档检查通过。三份旧CSV的只读副本各50000行，经独立复算、实际三格式报告生成、原生严格沙箱解析和完整质量投影均passed；故意损坏PDF后重新拒绝。这只是离线链路证据，不冒充真实模型验收。Ruff、Black、isort目标检查通过。mypy目标调用仍报告6个既有模块14项错误；同一基线对照错误逐条相同，本次文件无新增错误，不宣称mypy全绿。

原管理员后端版本保持；四个同版本普通测试账号的复测需要第4个临时密钥命名空间和临时第4额外槽，已单独请求用户授权，收到前不处理第4个密钥或改变容量。原三份失败会话继续保留，禁止离线修写成通过结果。

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"全量派生数值复算属于既有Host质量核验和文件交付，沿原DSH回合及同一私有check callback，不增加部署节点、数据库或研究执行引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有send/detail/check质量合同补齐来源与线程后scope复核，HTTP边界和部署图不变。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"共享service的本次变更仅FinGPT质量核验；Automation执行、授权、调度和投递沿旧合同，不增节点或权限。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"三个纯回归模块复用现有Python验收步骤和runner，不新增job、平台节点或依赖；安装CI和真实模型证据继续独立验收。","diagrams":[]} -->
