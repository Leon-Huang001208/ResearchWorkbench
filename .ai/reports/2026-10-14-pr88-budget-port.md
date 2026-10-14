# PR88 独有预算增量

macOS 功能开发，本地基线 master `38c180953`。两项独立实施为私有持久账本与 launcher/guard
接入；只提取预算，不恢复旧模型存储。已确认设计见同日 budget-port spec。
原 PR88 保持草稿，不合并、不关闭；替代候选完成后再提供审查结论。

旧政策已过期，当前初始化、扣票和激活必须拒绝；历史时钟测试不能用作新的真实授权。
无真实 Key、无模型网络请求、无运行实例操作、无新依赖安装。受管 AES-only 身份限制不
改变正常 Native/Fernet。其他平台与真实模型以最终 SHA 保留 NOT_RUN 交接。

RED/GREEN、静态质量、规格/质量审查、本地回归和自动 CI 证据分别记录在
`logs/pr88-budget-port/`；后续新 SHA 不借用旧提交 CI。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"现有launcher及guard读取显式实例预算并通过私有RPC扣票，不增加DSH引擎、部署进程或自动激活。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"新增预算模块为内部私有账本，不增加公开HTTP路由、设置页或研究正文库。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"当前加密凭据、私有卷和既有双进程部署保留，预算只在显式控制下消费。","diagrams":[]} -->

独立JS审查发现只停止流读取不能abort上游的P1；现已通过公开agent/request归属与Agent.cancel修复，真实固定SDK的无网络合成fetch链断言原signal abort、0迟到chunk。测试夹具首次失败日志保留，不改SDK或新增依赖。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"新增预算精确路径映射与L4必需ledger/guard测试，继续使用同一planner及Git绑定receipt，其他平台门不裁剪。","diagrams":[]} -->
