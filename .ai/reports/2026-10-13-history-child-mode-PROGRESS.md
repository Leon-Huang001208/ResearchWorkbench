# 历史子会话模式兼容修复

宿主macOS；缺陷修复；Native读路径及同平台CI验收；其他平台不冒称通过。

8088 GET /api/research/sessions返回503 protocol_error“原生子会话状态未知”。只读核对51个本地父会话中10个含19个unknown模式子会话，原生归属及活动可验证且都不运行。列表与详情使用严格执行模式目录，错误扩散阻断列表。

新增运行/非运行历史子会话API回归先失败2项；列表及详情改用既有activityOnly通道后2项通过。未知模式不猜测子历史地址，显示明确限制；继续/中断等控制路径未改变，活动/归属不确定仍拒绝。

完整API/协议/取消回归122通过；Ruff/Black/isort及文档/架构检查通过，独立只读复审未发现权限放宽。真实8088尚未应用。未清除历史、未调用模型、无新依赖。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"History list/detail reuse existing verified activity RPC and existing child error fields; no endpoint or engine topology change.","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Automation retains its existing parent session consumer; historical mode availability does not authorize execution or imply idle.","diagrams":[]} -->
