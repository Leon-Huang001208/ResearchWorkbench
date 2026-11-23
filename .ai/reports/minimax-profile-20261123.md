# MiniMax 添加阻塞修复

macOS Mac mini，Web 功能修复。线上无 Key POST model-profiles 实际返回 503 model_activity_unknown。旧 FinGPT 已由 AlphaDesk 退役，但连接 gate 仍读历史 running；两条 Claw 的权威投影 completed 与旧索引 running 不一致。复用退役判定及 detail 核对，不删除或改写历史。保留 Runtime/受理/子研究/交付阻止条件，并补 AlphaDesk task 活动检查。

现场观察前端协议隐藏 select 的 option 被禁用后 FormData 丢 provider（禁用来源未证实），改用 hidden input；不读取或输出 Key。已有 DeepSeek 连接保持使用中。

RED: 两个针对退役与历史完成的回归失败；两个未确认历史反例通过。GREEN: model_profiles 原模块20测试通过，JS原5测试通过。最终13项新增及相关回归通过，含真实detail与native history完成/缺失完成事件、退役native/receipt/children反例和QA task。JS6项通过。候选gate读取现场DSH及原Host权威detail后通过，历史索引未改写。ruff/isort、文档治理、进展说明与diff检查通过。CI、上线及真实MiniMax生成分别验收；无Key不调用供应商。

Product-Progress: not-required — 本次只修复模型配置保存既有故障，不新增公开产品能力说明。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"复用既有退役判定与权威历史投影修复模型配置准入，不改变运行节点、接口或持久数据结构。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅将模型服务商协议身份改为隐藏input提交，页面布局、导航与接口结构保持既有设计。","diagrams":[]} -->
