# 私网事件明确动作转发修复

宿主macOS Mac mini；功能修复及已授权常驻补丁。基线为已接受的
`a76ecfdfb1b1b7a35c508d15ccf16222ed20423c`，任务为 `market-event-intent-fix-20261106`。

## 实际复现与根因

认证私网浏览器在事件工作台点击“手动更新／分批回填”，选FOMC、year留空，Host返回403
`explicit_user_action_required`。事件写入未受理，采集checkbox仍未勾选。前端write使用
`userAction:true`，core确实创建 `X-Research-User-Action:?1`；账号网关的REQUEST_HEADERS
未保留该头，Host按原严格规则拒绝。原拒绝及页面证据保存在主任务的私有验收记录中。

修复仅保留客户端已有意图，不生成或升级缺失/非法标识；认证、同源、账号绑定、后端key、
凭据剥离及Host校验均保留。未改生产常驻文件、后端门、模型或采集计划；新候选须验证后再部署。

Product-Progress: not-required — 本轮仅修复私网既有明确动作标识转发，不增加界面入口、事件覆盖、评分公式或用户配置，既有事件功能进展条目继续适用。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"在原浏览器到账号网关再到Host的既有请求边上保留客户端意图，不新增节点、接口、权限或研究执行链；原认证、同源、租户key和Host明确动作门保持。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"后继Native封闭身份复用原三锁、全账号保全、严格关闭及永久恢复源码，不改运行节点、Docker互斥、依赖或部署拓扑，实际切换需新候选独评和CI。","diagrams":["01-deployment"]} -->

当前仅记录复现和实现边界；实际测试、评审、CI、补丁切换、正常手动事件与关闭状态将分别留证，不能预先标为通过。

## 网关产品检查点前证据

最小修改只有允许集增加 `x-research-user-action`。真实账号Store、登录网关、Host中间件及
后端key合同测试覆盖24个不同节点，正式WIP三批16/12/4项均通过并退休；最后4项加强为
真实source_job completed且imported=1后再次通过。来源下载为测试替身，不冒充实际网络源或生产入库。
缺失/非法标识、匿名、跨源、旧页面及浏览器伪造凭据的原拒绝断言保持。
Ruff/Black/isort通过；独立Python/安全只读复审无具体P1/P2。最终候选与实际部署仍待后继阶段。
