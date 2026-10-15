# Hot研究模型流装配接续

macOS功能开发，在既有独立worktree从181636494继续。上一goal轮为PROGRESS：预算私有RPC
已提交并经PG验证。本轮把预算消费者接入已有Runtime overlay和Host私有数据HTTP通道。
完整原目标不变，正式研究、恢复、持续来源、计划简报、Docker及候选安装/CI仍需完成。

完整messages/system/tools/toolHistory等请求经过JSON冻结和确定性hash，UTF8字节加2048
协议余量登记输入上界；prepared配置必须同route/model/output cap且normal maxRetries=0。
同run+实际请求生成稳定call UUID；busy/unknown不重发，reused重放，回执先保存后输出。
stream有界至1MiB/8192块，usage+终态完整才提交。发送登记异常不退款；只在确认未开始
dispatch时取消预留。子会话核对真实ancestry和根工作区，费用仍归原Hot session/run/scope。

Host先验证私有DataHub key、owned Runtime、Store purpose/hot_origin、PG run/session/instance/
manifest，再转入现有签名RPC；browser user-action不能授权票据。完整回执/缓存可走大帧，
普通帧原限保持。稳定model错误按操作白名单保留，任意后端文本遮蔽；日志只记录稳定事件。

审查修复：receipt/cached await及逐块输出均检查取消，已计费回执保存后取消不会发布；
普通外部workspace透传，不因Hot未配置阻断；managed祖先的child仍严格核验。JS限定最终
复核关闭两项问题。Python初审两项MEDIUM（错误分类、大帧边界测试）已修改并加真实
loopback/HMAC/错误码/归属反例；最终复核两次因模型capacity失败，不能写成最终Python审查PASS。

stream先RED（缺模块）后GREEN；目标stream/guard/credentials25 PASS。相关Python146 PASS。
真实固定48504 SDK、合成凭据、完全替换fetch的离线Anthropic SSE1 PASS，验证真实wire bytes
不超过登记bound、实际usage转换、一次发送、receipt先于输出。不会外连，也不以合成usage
冒充真实费用或真实PG持久化。默认official retry=5仍被新桥拒绝；专用零重试装配待验。
本轮未resolve用户真实key、发送vendor请求、迁移原库、启用原实例、扩额或发布。

最终Web398 PASS/1 SKIP，相关Python168 PASS；Router所选运行回归472 PASS/1 SKIP，
治理110 PASS。36文件项目约束、架构、文档治理、Python索引及whitespace PASS。
初架构检查因合并import不被挂载提取器识别、API库存缺条失败，已拆分import并登记实际
POST接口；未修改或放宽门。Ruff/Black/isort尚未安装获批，保持NOT_RUN；新安装/Mac CI亦NOT_RUN。

下一步先配置/验证当前Runtime官方route的受控零重试，补reserve回执丢失的未发送预留处理，
再接现有执行API的run/delivery映射、真实DSH研究及产物。完整Goal ACTIVE。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"在既有DSH、Host私有数据通道、Hot签名服务及同一PG账本内装配预算消费者，无新增服务/队列/执行器；正式研究与零重试激活仍待，图11既有研究与预算边界保持。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"overlay新增同Host内预算插件，复用现有session registry与私有HTTP，不改变DSH进程/工具授权/数据目录；普通外部会话透传，模型实际激活未认证。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"在已有私有数据HTTP边界内增加Hot账本操作，仍由同一ResearchService/HotWebService和PG Owner持有状态，不新增服务拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"HotManager大帧和账本投影复用原Native实例/模式身份及签名协议，没有新的运行模式、安装依赖或跨模式写者；Docker验收仍未执行。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"导出原私有control读取器供内部预算adapter复用，Provider/来源查询和冻结副本合同保持，没有新增数据源或外部网络授权。","diagrams":[]} -->
<!-- architecture-review {"group":"mcp-runtime","structure":"unchanged","reason":"预算adapter使用原私有数据通道，不注册MCP/Skill/模型工具，不改变MCP授权或能力目录拓扑。","diagrams":[]} -->
