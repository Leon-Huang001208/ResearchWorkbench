# FinGPT 网关配置接线修复

Mac mini / macOS 功能修复，接续原替换任务和PR330。75f9正式删除5旧聊天/留1数据资料；随后网关启动未采用既有配置helper导致绑定比较失败，原流程已自动rolled_back7dc/preserved=true；旧聊天没有回填。真实原2快照/6数据回执/1正式报告和Claw核对通过。

一行修正实际start_gateway配置来源，补调用实际方法的前向和回滚回归，不只测试helper。不新增模型、依赖、备份、部署或恢复框架。平台原生Windows/Linux NOT_RUN。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"只将原网关启动配置来源改为已存在且已审的同一配置函数，锁、检查点、身份、启动顺序和原回滚保持，没有新增运行节点或恢复机制。","diagrams":[]} -->
Product-Progress: not-required — 原替换入口的配置接线更正，不新增用户能力。
