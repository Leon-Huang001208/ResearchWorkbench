# Mac Python实际映像修复

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"只把原gateway进程身份核验连接到内核实际映像，保留完整argv、起始时间与listener边界，不增加部署节点或研究执行路径。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"在既有Mac Bootstrap环境步骤增加stdlib只读探针，无新job、runner、依赖或平台dispatch，原Checks复用近处回归。","diagrams":[]} -->

macOS Web管理平面。真实PR151部署预检拒绝gateway_process_unknown，尚未安装恢复agent、停机、切源码或写业务数据。复现显示Homebrew bin/python3.12启动器exec到同framework的Resources/Python.app；旧代码只按启动器resolve匹配ps argv0，误拒绝真实进程。

先补原生缺失接口失败回归，再通过macOS proc_pidpath绑定当前生产venv与gateway实际映像。argv0仅允许配置路径/resolve/内核映像三种精确值，完整模块/root、PID起始时间与listener继续匹配；发信号前再次验证映像。读取失败或外来映像仍拒绝。真实生产只读探针的exact argv、same kernel image、owned listener均true，无服务变更。非Mac原生探针保持NOT_RUN；无依赖或模型调用。

本机近处106 PASS、协议81 PASS、Node治理/路由229 PASS；项目约束、文档治理、Python索引及ruff/black/isort通过。独立源码复审APPROVE；Mac Bootstrap在原步骤加入绝对venv调用的原生映像断言，最终同树CI与真实部署另证。
