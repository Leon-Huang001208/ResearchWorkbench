# Wind 历史读数精简

用户提供的 Wind 截图只用一个“幅”字段，百分比后括号保留涨跌额。本次仅修改 `asset-chart.mjs` 的共用读数投影：`幅 -0.21%（-0.58）`，不再同时出现“涨跌额”和“涨跌幅”。红涨绿跌、零值中性、缺少上一周期收盘的“—”、日周月同周期计算、振幅、量额及图表操作不变；tooltip 与顶部使用相同输出。沿用原图表日志、异常边界，不添加逐次指针日志。

最小复现先改近处周/月与颜色断言，原实现出现3个预期失败；窄修后78项通过，日志在 `logs/asset-wind-readout/red.log` 与 `green.log`。完整 Router、独立评审、候选 CI、同候选 Mac 安装及实际部署/认证页面验收各自留证，未执行阶段不认证通过。当前任务是 macOS Web 功能调整，不安装依赖、不修改凭据、数据库、冻结数据或研究引擎。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅合并浏览器历史读数字段文本，原始数据、计算、HTTP、持久化及DSH/Host拓扑均不变。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"纯展示调整，账号隔离、授权、数据查询和部署边界保持，未引入来源或共享状态。","diagrams":[]} -->
