# 私网事件明确动作与市场旧页入口修复

宿主macOS Mac mini；功能修复及已授权常驻补丁。基线为已接受的
`a76ecfdfb1b1b7a35c508d15ccf16222ed20423c`，任务为 `market-event-intent-fix-20261106`。

## 实际复现与根因

认证私网浏览器在事件工作台点击“手动更新／分批回填”，选FOMC、year留空，Host返回403
`explicit_user_action_required`。事件写入未受理，采集checkbox仍未勾选。前端write使用
`userAction:true`，core确实创建 `X-Research-User-Action:?1`；账号网关的REQUEST_HEADERS
未保留该头，Host按原严格规则拒绝。原拒绝及页面证据保存在主任务的私有验收记录中。

修复仅保留客户端已有意图，不生成或升级缺失/非法标识；认证、同源、账号绑定、后端key、
凭据剥离及Host校验均保留。未改生产常驻文件、后端门、模型或采集计划；新候选须验证后再部署。

Product-Progress: not-required — 本轮恢复已说明的事件手动操作与市场旧页可见性，不新增业务页面、事件来源覆盖、评分公式或用户配置，既有功能进展条目继续适用。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"在原浏览器到账号网关再到Host的既有请求边上保留客户端意图，不新增节点、接口、权限或研究执行链；原认证、同源、租户key和Host明确动作门保持。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"后继Native封闭身份复用原三锁、全账号保全、严格关闭及永久恢复源码，不改运行节点、Docker互斥、依赖或部署拓扑，实际切换需新候选独评和CI。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"恢复市场模块已有五个页面的可见链接，与统一侧栏隐藏重复tabs规则一致；无新页面或数据执行边，不修改旧行情控制器、主题或研究引擎，实际全壳层回归另证。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"修复复用原Gateway测试、Node模块导航与既有全壳层e2e夹具；安装及CI沿原job/runner/依赖/时限，不增加平台dispatch或测试执行器。","diagrams":["08-iteration-docs"]} -->

## 同页旧入口实页缺口

a76私网完整壳层中，市场模块栏只有“市场总览／研究工作台”，而全局导航CSS隐藏内部
`.market-tabs`，导致行情分析、沪深北行情和板块资金三个可见链接均为0。原深链和业务内容
仍在；修补仅恢复模块侧栏五项，保持全局隐藏重复tabs及旧控制器不动，需真实CSS/壳层回归。

旧入口修补的Node断言先RED、后focused33/33 PASS；既有loopback全壳层/真实CSS浏览器
验证内部tabs实际隐藏时五链接仍可点击，并覆盖选中、后退、reload、折叠与390px抽屉焦点。
无console/runtime/external或真实业务写入；旧视图的5次刷新均为显式mock记录，不代表生产取数。

当前仅记录复现和实现边界；实际测试、评审、CI、补丁切换、正常手动事件与关闭状态将分别留证，不能预先标为通过。

## 网关产品检查点前证据

最小修改只有允许集增加 `x-research-user-action`。真实账号Store、登录网关、Host中间件及
后端key合同测试覆盖24个不同节点，正式WIP三批16/12/4项均通过并退休；最后4项加强为
真实source_job completed且imported=1后再次通过。来源下载为测试替身，不冒充实际网络源或生产入库。
缺失/非法标识、匿名、跨源、旧页面及浏览器伪造凭据的原拒绝断言保持。
Ruff/Black/isort通过；独立Python/安全只读复审无具体P1/P2。最终候选与实际部署仍待后继阶段。
