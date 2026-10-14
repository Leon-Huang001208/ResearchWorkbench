# PR100 最终主线整合

macOS Web 功能开发复验，来源候选 `7cd3178e`，同步基线 master `d8127c30`。
#88 已经按确认关闭且未合并、未删除分支；#100 本轮不合并、不开启自动合并，
不触发 Windows/Linux/桌面 workflow，不读取真实 Key 或修改日常实例。

保留主线 #95 ETF、#96 AES/Fernet/Native 加密凭据与来源、#90 原生 Todo 完整性及
#107 持久预算、已认证 owner/signal 的截止取消、旧政策过期拒绝和默认不激活。
PR100 兼容模型、外部来源、失败活动、reasoning/usage、交互和并发私有目录修复保留。
新增同会话计划与 reasoning 共存回归，防止语义叠加丢失其中一种投影。

旧 Wind adapter 公式调度/日志与对应专用单测不属于本次 Web 候选；从候选中拆出并
保留原始 `7cd3178e` Git 提交及 `logs/pr100-after-master/deferred-wind-compatibility.patch`。
不是放宽桌面门或声称 Wind 实验通过；后续独立适配/验证后再交付该增量。

复验按最终 SHA 的完整 changed set 路由。本轮新证据位于 `logs/pr100-after-master/`；
旧 #100 回归、浏览器与 CI 仅是历史来源，不替代新候选验收。真实模型与其他平台保持
NOT_RUN 并按候选 SHA 交接，跨平台发布状态与 Mac 本任务分开。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"融合兼容模型和来源控制到既有DSH与私有桥，保留预算owner信号与加密身份，没有新增引擎或部署。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"在既有模型设置和研究空间叠加来源及计划恢复，保留原页面导航和单一计划渲染。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"同一原生日志保留reasoning与canonical及兼容计划字段，HTTP和SSE沿既有边界。","diagrams":[]} -->

独立Python复核发现reasoning-only消息被非空text过滤丢失；4项流式/取消/完成场景先RED，
现以text或非空reasoning过滤保留消息，协议/事件恢复79PASS。旧全量运行不认证该后续修改，
最终候选另跑完整相关闭包，失败证据保留。
