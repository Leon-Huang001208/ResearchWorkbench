# 资产周期读数及 Wind 副图修复

- 宿主：macOS；Web 功能修复。未进行 Windows/Linux 原生验收。
- 复现：月K顶部错误地取月末单日 OHLCV/前日收盘；聚合蜡烛与读数冲突。合成反例上周期收100、本周期收140，最后一天150→140，预期+40%，旧实现-6.67%。原失败 logs/period-return/red.log。
- 根因：renderMarketTerminal 和 syncLabels 在 source=day 时无视显示周期而直接从 daily 投影；图上 candle/tooltip 已使用 aggregate。
- 修复：读数统一取 bars[activeIndex] 与上一根同周期；日线 selectedDate 与筹码缓存保留。缺少上一周期或聚合换手/均价不冒用单日日值。
- UI：底部单一＋打开原完整目录/常用/参数，无重复管理入口；面板×关闭，标题替换。日期仅最底部轴及该轴十字线标签可见，筹码横向数值轴无竖网格。
- 模块/结构复核：仅原浏览器纯计算投影/控件，不新增模块节点、HTTP、持久格式、依赖、服务或执行引擎；架构图仍准确。原 guard/logger、错误处理与偏好权限边界保持。
- 初步验证：资产JS 187 PASS；后续完整Router、独评、CI、安装、实页与授权常驻部署分别留证，不以局部通过认证其他门。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅原资产行情组件改周期读数投影与副图控件呈现，保留原页面/图表生命周期与主题节点；没有新页面、服务或研究引擎，既有UI架构图准确。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"聚合K线取代错误单日读数只发生前端；观察、历史、冻结、偏好HTTP及账号数据格式不变，所选日与筹码截止仍独立，原工作区数据与API图准确。","diagrams":[]} -->
