# 网关退休与大保全摘要恢复就绪性

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"仍为原管理平面内的网关事务，仅修正进程退休判定与完整保全journal预算，不新增节点、研究引擎或业务数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"Mac Bootstrap原步骤补临时子进程和大journal探针，Checks复用原文件，无新job、runner、依赖或跨平台dispatch。","diagrams":[]} -->

macOS Web管理平面。PR152真实部署在SIGTERM后遇到尚未回收的进程表记录而误报PID复用；完整保全journal实际1,231,959字节，自动恢复的通用1 MB reader拒绝。保持原journal不改，在primary supervisor/admission EX内匹配冻结SHA、按16 MB私有fd有界读取，再调用原已评审recover_locked完成回滚；gateway健康200、绑定primary6c、preserved=true。无强杀、数据覆盖、依赖安装或模型调用。旧恢复agent/artifact已按原摘要归档退休。

先补两项实际失败回归：真实Mac子进程延迟reap复现gateway_pid_reused，大manifest经正式recover复现resident_record_invalid。实现等待PID消失，变化或未回收只延后；专属journal 16 MB私有fd reader/writer与首次信号前headroom校验，通用配置门不变。回归另覆盖边界、短读、替换、权限、硬链与真实不可变artifact主入口读取。Mac CI原step增加同一无业务夹具；最终CI及后续生产结果另证，未验证平台不冒充通过。

本机目标/协议/本机集成305 PASS、1既有平台SKIP（23.88秒），Node治理/路由229 PASS；ruff/black/isort、完整路径约束、文档治理和Python索引通过。独立评审发现并补齐FIFO在fstat前阻塞的风险：使用O_NONBLOCK，同样拒绝非regular；隔离子进程负测快速拒绝。新增Mac Bootstrap原生临时夹具精确代码已在本机实跑PASS，不访问常驻端口或数据。
