# 事件研究 Mac mini 封闭部署入口

宿主：macOS；任务类型：功能开发／受管部署入口准备。本平台范围为本机离线验证及适用 Mac CI；Windows/Linux Native 未执行。

固定EVENT前版db2ae9a48ceca365852072e622aa6627aa7d0b83；功能a398a29429a1c0bdddd34ce50bc336fd6e20f2ee→维护60416994f88eeead8a3891dbe9a7dfd617c566fc→用户已授权MCP主线58ad352eeb925805ff00f46139a073fda15163d3→安全闭包65a016b3525f0a395ee221bf44f1b208818b03e8。仅a398→604要求app树相同，所有段必须祖先相连。沿原 v4 事务、三锁、BirthFence、完整资格及全账号原件保全，不进入 TRIAL，不改 controller／白名单／日程，不安装依赖或接触生产（worker 范围）。

实现：封闭 apply-events；原 g.verify_primary 后新增严格空 Native list 与全账号事件采集关闭证明；准备、idle、验证及恢复重查冻结证明。事件原件由 retention lock／snapshot_events 校验后仅在内存 SQLite query_only 查询最新版本，WAL/SHM/journal／孤儿／enabled/unknown／未决采集均拒绝。保全仍使用原 @events。

## 本轮65a组合更新

仅EVENT目标gateway配置持久严格False；原g.health/fenced readiness链保持，附加local/private health实际Facade字段is False，以及原plist/loaded job、目录/仓库、PID/birth-command/listener/native image的窗口一致性。规范JSON区分False与0；恢复重查配置，rollback原gateway_config逐字段恢复，旧db2缺字段仍缺，不索要旧版不存在的新health协议。原日程off／Native list／三锁BirthFence／@events恢复不改。

本轮最近3例先真实RED（新pin缺失、未persistFalse、health缺席未拒绝），同nonce/root经独评完整metadata同gid副本保全后GREEN3/3并原retire。再运行19项实际local/private HTTP读取协议及固定组合祖先Git反例、7项原真实事务故障切点，全部WIP通过/0skip/原retired；合计29个本轮节点。证据`logs/event-mcp-profile-red.*`、`logs/event-mcp-green-attempt/`、`logs/event-mcp-health19.*`、`logs/event-mcp-transaction7.*`，计划/摘要另列。测试仅替换HTTP/OS运输，原Gateway health解析和Operations.verify执行，真实operate primary/idle既有回归保持。

本轮未重跑完整legacy module；旧7881正式2480/2944、余464未跑的incomplete事实不充当前组合证明。当前WIP不是最终exact-SHA CI或部署/业务接受。最终Root按完整changed-set冻结本平台闭包，重新取得必要评审/原三CI/Mac bootstrap；其他平台保持未执行状态。

## 历史准备证据（不充本轮组合验收）

验证：新增两例先真实RED（缺EVENT实现，2 AttributeError），随后同root/nonce受审恢复实际GREEN 2/2，原RED四证据与完整夹具核验归档保留。EVENT相关WIP矩阵共176例，9批每批不超过20例顺序执行，全部实际通过且受管receipt均为retired，见`logs/event-wip-summary.json`及`logs/event-wip-plan.json`。矩阵覆盖固定pin、真实Git并集/blob/mode/祖先/额外变更、全账号保全、每阶段恢复、真实operate的Host/Native/原idle门、事件采集enabled/unknown/未决、SQLite sidecar/未知schema和冻结证明漂移。批01/04/06曾暴露测试夹具缺字段／映射／幂等key过短，经修正并分别独评同根恢复，失败原件与归档仍保留；未放宽产品门。Black、isort、ruff目标检查及git diff --check通过。

证据边界：以上为未提交工作树WIP验证，base candidate字段不是当前源码的exact认证；最终完整module、独评、Router、合并SHA原三CI及Mac bootstrap仍由主任务执行。此前未用confcutdir的pytest因root conftest缺sqlalchemy退出4，仅为错误测试入口，未安装sqlalchemy。

未执行：真实服务调用、模型／厂商、日程修改、部署与运行切换。最终合并 SHA 必须重新取得独评、Router、原三 CI／Mac 安装资格；产品或旧工具证据不能冒充。实际部署、认证页面／业务验收和收尾由主任务另证。
