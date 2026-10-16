# Host元数据专项兼容升级

macOS功能开发与本机Native部署；用户明确授权专项升级，不绕过门禁、不终止研究。起点master5ba7578af，生产02c086b16；原自动门拒绝四个Host文件及两份生成文档。

显式入口绑定预期旧版、PR122 Host Git blobs、精确目标及干净同Git源工具checkout。GitHub merged PR、独立review、三CI实际tree仍是前提；自动兼容清单与固定LaunchAgent artifact不变。专项工具自身只能由已验收目标提供，不支持其他未知代码或依赖/Store变化。只读metadata shape gate无迁移，继续原空闲/EX准入/lifecycle/journal/health/rollback；成功才审计和刷新baseline，失败或延后不更新。

验证与真实部署结果记录logs/host-metadata-upgrade-20261016及受管回执，未执行不标PASS；无模型调用，Windows/Linux原生验收NOT_RUN。

<!-- architecture-review {"group":"bootstrap","structure":"unchanged","reason":"既有macOS控制平面增加单次已审内容的显式兼容复核，不增加节点或执行器；原监督器、生产根、生命周期栅栏和回滚边界保持。","diagrams":[]} -->

只读生产预检：58个会话，Claw/FinGPT项目与navigation命名空间目前均未建；类型兼容，未写index。初轮resident33项通过；新增拒绝/空闲/恢复测试继续验收。所有检查复用现有解释器和已缓存工具，没有安装依赖。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"专项入口只使用原macOS Native resident bridge与固定生产根；没有模式切换、容器或共享数据迁移，Docker和其他平台保持独立验收，新增baseline审核仅属于控制平面。","diagrams":[]} -->

本机初步验收：resident专项35项通过（既有Starlette弃用告警1），治理/架构JavaScript111项通过，Ruff/Black/isort目标文件通过；架构完整性和文档治理通过。未知代码、Host内容变化、错误common/dirty源、隔离候选、恢复journal、迟到master、deferred/rollback基线不变均覆盖。独立Python审查当前无具体P1/P2，最终SHA待绑定。
