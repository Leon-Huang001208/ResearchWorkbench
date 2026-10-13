# Local models 安全融合任务

宿主：macOS。任务：功能开发与修复。交付止于 PR，不合并、不自动合并、不升级日常实例。
基线 master：566523a0e0093f113ad12e57c3ef5cd0a8e0a87a。
来源：6ad0b275c86c8af03389af824451a6244759e61e。

## 结果与设计

在独立 worktree 分块融合交互、模型协议与 DataHub；保留 Claw 项目/草稿、研究深度/范围、
原生 Todo、证据笔记、HTML/Word/中文 PDF、准确交付状态与既有权限。
子会话关系修复已在 master，保留其严格 parentSessionId/origin/running 校验，不退回旧字段。
不导入重复 tar/patch/源码副本或机器截图，也不把旧任务验收报告作为本次证据。

四项修复：HTTP 认证入口在读取秘密前拒绝；兼容传输不认证未知模型工具能力；
推理块在正文/工具块前结束；异常、空对象及未知脚本结果失败关闭。
复审另修正文重试资格绕过、JSON/HTML 编码后的凭据反射，并补回归。
保留原 persona 的数据口径、缺失说明、文件重开、Tabbit 审批与四子任务限制。
未经证实的道乐 HTTPS 地址不猜测；原 HTTP 目录明确 blocked。成交量单位未经证实时不换算。
未披露模型容量时使用32768压缩预算，显式配置可覆盖，不把所有模型声称为1M上下文。

## 已执行与限制（提交时快照）

- 四项核心负向先失败后通过；协议闭包40项通过。
- UI专项157项通过；兼容协议19项通过，含真实固定DSH Loader/isolate/pruner/context消费。
- DataHub四模块157项通过；后续external编码反射闭包35项通过，计数重叠不相加。
- Research Web JavaScript最终整套417项、415通过、2项既有跳过；重试草稿保护亦通过真实事件回归。
- 架构/文档/Actions/跨平台仓库合同110项通过；文档治理、改动文件Ruff/Black/isort通过。
- 导入闭包Mypy 58错误，与未修改最新master的诊断逐条完全相同；全Web Ruff6错误，master同样6错误。
  不把相关新模块有限Mypy通过替代完整类型检查，不修改无关债务或放宽规则。
- 完整Python扩大检查：3412通过、7失败、10跳过。两项新增AKShare断言已修正；
  其余五项在未修改master上逐项复现失败（能力目录计数、Native临时HOME状态、框架凭据夹具、
  卖方Skill目录计数及资源脚本）。保留完整套件FAIL，最终影响闭包复跑另行记录，不替代此失败结果。
- 隔离Native安装/健康及GitHub CI仍在执行，最终状态以PR当前检查和后续回执为准。
- Windows/Linux原生验证、真实供应商与真实模型推理未执行；不读取或迁移现有实例秘密。

测试依赖仅在用户授权的任务环境安装，不修改产品锁、全局Python或现有服务。
日志留在任务logs目录；只上传脱敏摘要，不上传运行时认证、供应商秘密或原始请求。

## 结构复核

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"共用原生renderer/controller融合停止超时和重试资格，不新增框架，Claw、深研和报告路径保持。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有FastAPI Host继续负责会话和DataHub桥接，新增投影字段不创建研究循环，原准确失败语义保留。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"外部Provider扩展既有Broker和会话快照，HTTPS及反射检查留在Provider边界，不新增数据库或调度器。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"共享service只保留精确工具验证，日程草稿、锁版本确认和原Automation监控合同完全保持。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"固定DSH内注册兼容协议和隔离压缩组，安装器、唯一执行循环、Tabbit审批及进程所有权未扩展。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"external_data工具复用已登记准入和版本目录，未知endpoint/model不获得深入研究或MCP权限。","diagrams":[]} -->
