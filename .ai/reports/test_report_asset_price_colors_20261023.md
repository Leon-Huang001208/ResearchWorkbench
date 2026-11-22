# 资产红绿行情与Wind参考副图管理

任务asset-price-colors-20261023；macOS Mac mini，Web功能开发。用户追加要求开高低收、涨跌幅参考Wind。

沿用已批准精炼布局、万亿格式、图表生命周期及数据。开高低收相对前收分别着色，不按整根蜡烛方向套色；当前价使用同快照前收/来源涨跌，涨跌额和幅各自按正负。采用现有主题danger/green变量以保持明暗对比，只作用于资产数值，不改变风险/成功状态语义。价格无效/非正、涨跌零/缺失保持中性。历史选择与局部更新重用纯分类器，updateAssetSummary同步class。

本地资产JS184PASS，约1.79秒。独立评审指出无前收且零价会借来源跌幅着绿，已加有效正价格guard和回归。最终Router、独评绑定、宽窄明暗、同候选三CI/macOS干净安装、固定新profile及常驻验收另行记录；不预先标为已部署。此前精炼布局v6已部署0e0022ac，保全true，本颜色补丁尚未部署。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅既有资产组件数值class与主题变量，原DOM层次、搜索、页签与图表实例不变，无新页面/服务；现有UI图仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"仅前端投影暴露同快照前收并格式化数值，不改HTTP/冻结/Provider或研究引擎；原观察和数据流图仍准确。","diagrams":[]} -->


用户已确认副图v0并授权补齐OHLCV指标。本次新增15类计算、封闭参数、账号常用排序与面板增减/替换。原AF默认MA/MACD/KDJ/RSI/BOLL数值保持；新指标参照公开TA-Lib定义，未声称Wind私有公式一致。W&R采用正0–100；ATR/DMI Wilder种子，CCI14平均绝对偏差，SAR初始/反转固定参考593ff538；EMV按(volume/1e8)缩放。金额/股本、估值/持仓并不从OHLCV推造。

正式平盘golden曾发现CCI均值浮点误差被微小偏差放大，已以中心差均值修复并保留回归。独立预审覆盖44583前缀字段、9000根约279ms；主回归覆盖SAR反转、线性/平盘、缺量/零量、预热/周月和6001条。待最终计数、浏览器矩阵、精确SHA独评、Router/三CI/macOS、固定部署及保全，未标记完成。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks只扩展封闭副图参数回归清单、原Bootstrap校验两个离线模块；没有新job、runner、依赖、发布流程或研究质量门，现有交付状态图保持准确。","diagrams":[]} -->

独立后端评审复现A→B→A后旧偏好响应污染回滚基准，已增加独立账号代次：排队发送/成功/失败均检验epoch，并在账号变化时释放新账号队列；正式ABA回归验证旧排队请求不发送、旧响应不污染刚重读设置。

第二独评发现明确新账号偏好缺少可选键时会沿用旧图表参数，已改为显式偏好使用默认值，并将账号纳入图表身份/配置签名。新账号重置日期、筹码默认与参数、关闭旧模态草稿，原冻结数据保持；正式回归覆盖同资产跨账号。浏览器另发现旧CSS590px上限压住第三副图后的控件，已仅在现终端解除上限，实际DOM/canvas均676px、控件从其底部起排。新增真实固定ECharts对6001条/15面板全部series view绘制及mounted light曲线可读性检查通过。
