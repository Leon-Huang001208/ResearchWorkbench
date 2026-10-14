# Hot正式执行启用与恢复接续

macOS功能开发，既有隔离worktree从db346d092继续。上一Goal轮是实际PROGRESS，完整目标保留。
启用Hot/model的同项目私有settings才在Web Runtime准备时选择official normal/maxRetries=0；
缺失/坏/foreign配置不加载Node或秘密，不阻断基础Web。配置影响本实例官方provider，须重启。

execute API固定question/md-docx formats到不可变deliveryKey，复验固定快照/证据manifest，
PG先登记execution_starting，随后只走现有ResearchService.send。受理丢失/重启查询原生
user/message稳定marker，不重发；未知executionStarted=null。无receipt的确定前置错误
标failed/not_submitted；已有受理后failed不能报未执行。保存run→session/delivery映射，
尚未同步实际终态/产物，页面动作也未接入，不以受理或mock替代真实研究完成。

停止态、迁移owner、匹配instance/token的model-terminate现在能显式取消DB证明未发送的
reserved（dispatched_at NULL、无receipt），原子归还其预留。已发送/unknown仍不退款；
同操作UUID重放不重复退款。真实PG测试覆盖原有收费保留及新取消；初断言audit count未随
新增取消调整而失败，改为5（原2+取消1+CLI2）后PASS，失败日志保留。

fixture原先不清理随机资源，本轮加入显式创建后owned标记与精确清理。本次失败留下一个
schema/role，用本次日志时间窗、17迁移checksum、零成本synthetic scope、零产品行、唯一role
及无活跃/跨schema依赖审核后精确删除并确认；11个旧/不完整历史资源排除未动。

Python审查发现两项HIGH：CapabilityError/StoreError/OSError前置异常未分类，以及已执行failed
误报未提交。已补反例修复，9测试PASS，限定复核确认关闭；TS限定审查/typecheck PASS。
零重试/Runtime/model controls相关Python144 PASS+6subtests，真实model controls PG1 PASS。
没有发送vendor请求、迁移原库、启用生产或扩额度，真实研究/产物/安装/CI/恢复/Docker仍未完成。

最终相关Python165 PASS+6subtests，Hot单元47 PASS，typecheck及治理110 PASS。
项目约束/架构/文档治理/生成索引/whitespace PASS。本机describe固定ref显示主实例配置
存在、隔离研究home未配置，只返回配置状态，没有resolve或输出密钥；真实研究前仍需
受控复用既有凭据及停机迁移原schema15。完整Goal ACTIVE，原累计授权不重置/扩大。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"正式execute复用同ResearchService.send及原PG run/operation/预算账本，未新增执行器或队列；未知只查询恢复，实际产物尚未认证。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"在既有overlay按私有Hot启用意图选择官方零重试，不改变进程、目录或工具拓扑；缺失/坏配置维持基础Web可用。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"改变的是本实例模型策略和原有停机模型控制语义，不增加模式/服务/数据库；Docker/其他平台验收仍未执行。","diagrams":[]} -->
