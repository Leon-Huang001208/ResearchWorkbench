# 私有研究模型预算 RPC 接续

宿主macOS，功能开发，原隔离分支从51505f045继续。上一goal轮为状态核对，分类NO_PROGRESS；
本轮推进原完整Goal阶段四，不缩减正式研究、恢复、Docker或安装验收。

research.model.reserve/dispatch/unknown/cancel/receipt注册到已有签名Hot service，全部control权限。
run/session/call/ticket/scope绑定不能交叉使用；同一累计预算不创建新scope或授权。
服务计算固定价目费用，保存完整标准DSH流；已知有usage的失败保留收费与rejected标记。
缺usage/finish拒绝成功回执。仅已确认未发送的reserved可取消退款；unknown不自动重新发送。

独立TypeScript审查发现终态检查在事务外及签名帧容量不匹配两项P1。已将dispatch的绑定、
run/tariff核对与预算准入置于同一owner事务；真实PG在进入fence前推进completed的反例证明
拒绝发送且attempt仍reserved。receipt输入/reserve输出限2MiB签名帧以覆盖1MiB JSON编码；
普通操作原64KiB/1MiB限制不变。950000字节双向RPC及1500碎片PG回执均通过。

新回执测试先RED（缺模块）后GREEN。第一次集成误用startTransport签名，typecheck和实际PG
均失败；修复调用后通过，失败日志保留。审查指出测试隐式any，已明确RpcHandler参数类型。
最终Hot单元47 PASS、真实随机PG/签名RPC1 PASS；typecheck PASS。随机schema/roles随测试清理。
独立最终复核关闭两项P1并重新typecheck PASS。治理110 PASS，18文件项目约束、文档/架构、
Python索引和whitespace PASS；本候选Mac安装/CI、Docker及其他平台产品验证仍NOT_RUN。
本轮provider请求0，原实例未启用，未迁移原库、扩充授权、发布远端或改生产服务。

下一步接入私有Host/DSH llm/stream：由实际完整请求计算input bound，调用前登记、零重试，
在持久回执前保留结果，未知发送禁止自动重发，再完成真实DSH研究和产物。此接口单独通过
不证明实际模型费用已被限制。关注/定时简报、持续源重验、留出评价、联合恢复、Mac Docker、
干净安装及同SHA CI仍未完成，完整Goal ACTIVE。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"在既有签名服务和同一PG模型账本内新增研究预算操作，复用Owner事务与回执，不新增服务、队列或执行器；DSH流消费桥仍未装配。","diagrams":[]} -->
