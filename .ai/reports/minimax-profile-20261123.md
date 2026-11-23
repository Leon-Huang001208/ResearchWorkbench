# MiniMax 添加阻塞修复

macOS Mac mini，Web 功能修复。线上无 Key POST model-profiles 实际返回 503 model_activity_unknown。旧 FinGPT 已由 AlphaDesk 退役，但连接 gate 仍读历史 running；两条 Claw 的权威投影 completed 与旧索引 running 不一致。复用退役判定及 detail 核对，不删除或改写历史。保留 Runtime/受理/子研究/交付阻止条件，并补 AlphaDesk task 活动检查。

现场观察前端协议隐藏 select 的 option 被禁用后 FormData 丢 provider（禁用来源未证实），改用 hidden input；不读取或输出 Key。已有 DeepSeek 连接保持使用中。

RED: 两个针对退役与历史完成的回归失败；两个未确认历史反例通过。GREEN: model_profiles 原模块20测试通过，JS原5测试通过。最终13项新增及相关回归通过，含真实detail与native history完成/缺失完成事件、退役native/receipt/children反例和QA task。JS6项通过。候选gate读取现场DSH及原Host权威detail后通过，历史索引未改写。ruff/isort、文档治理、进展说明与diff检查通过。CI、上线及真实MiniMax生成分别验收；无Key不调用供应商。

Product-Progress: not-required — 本次只修复模型配置保存既有故障，不新增公开产品能力说明。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"复用既有退役判定与权威历史投影修复模型配置准入，不改变运行节点、接口或持久数据结构。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅将模型服务商协议身份改为隐藏input提交，页面布局、导航与接口结构保持既有设计。","diagrams":[]} -->

CI补正：第一候选文档校验缺复核标记，已按原架构不变规则补齐，第二候选Constraints与Mac安装成功。第二候选45096068329完整Web矩阵达到45分钟上限取消，未取得通过或完整测试结论。将本次精确模型配置变更纳入原Checks范围分支，完整相关Python模块/Host反例、原Node全套及原Constraints/Mac门保持。混入未知路径仍全量，不修改超时或测试断言。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只在原Checks作业增加模型配置精确范围和原分片runner调用，三项CI与节点、依赖及45分钟上限保持原设计。","diagrams":[]} -->
CI范围相关本地检查：governance37项通过，helper bash语法通过，相关Python209项完整收集成功；独立审查指出的helper触发路径已补入原PR/push paths。

第三候选45100922433相关Python执行出现9个setup错误、没有断言失败，全部属于test_model_connections旧api fixture未隔离系统凭据后端。在显式Fail keyring后端单用例复现后，复用test_api.isolated_keyring（仓库现有模式）补齐。相同Fail后端下完整209项：206 passed、3原平台skip（173.62秒）；governance37通过，独立Python审查通过。测试断言与模型服务代码未削弱。
