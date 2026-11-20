# Stage 注册接续

宿主为 Mac mini，本轮为 Docker 管理功能修复及本平台 stage 部署。
PR #316 已合并且真实 owner-handoff 已完成，旧 stage 的 2 GiB 预留已退休，原资源及未完成业务结论保留。
固定 `f6ec7bb22582564b626358a33936288e6fda70dc` 镜像已构建并核验，注册时 Docker 返回
`all predefined address pools have been fully subnetted`，留下本次四个空卷，尚无网络、账本或业务容器。

本次增加显式 CIDR 和 stage 注册接续，复用既有操作锁、归属核验、初始化和账本。
恢复前核对原四卷无引用且为空；网络存在时核对归属和 CIDR，缺失时按显式 CIDR 创建。
保持普通注册和既有记录读取合同。所有验证、现场部署及收尾结果绑定最终候选另存。

Product-Progress: not-required — 本轮仅修复管理员部署注册流程，产品界面与研究业务功能没有变化。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"沿现有管理器、操作锁和初始化接续同一stage资源，没有新增进程、部署节点或业务数据流。","diagrams":[]} -->
