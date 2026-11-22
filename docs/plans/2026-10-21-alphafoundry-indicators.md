# AlphaFoundry 指标区完整迁入 RWB（用户已批准）

保留RWB导航/账号/DSH；指标区以当前AlphaFoundry原页面为基线，连续展示基本行情、完整五图行情终端及右侧筹码、资金流、财务/前十股东/行业/事件/宏观五卡。取代七专题指标组织，新闻公告、自选、笔记、提醒、两融和其他补充数据留在指标之后，旧链接定位相应区域。首轮A股个股，不迁Agent委员会、数据库/协调器、合成主题和ETF/指数空壳。

## 完整指标与交互

- 基本行情：名称/代码、现价、涨跌额/幅、量/额、换手、市值、52周高低；不足一年改区间高低。
- 历史读数：日期、收盘、涨跌额/幅、开高低、均价、量/额、换手、振幅。
- 主图：MA5/10/20/60/120/250，各自开关；BOLL20上下中轨；裸K。
- 副图：成交量与VOL/量MA5/10标签、MACD DIF/DEA/柱、KDJ、RSI14与30/70参考线。
- 筹码：180价格桶，至少5根有效OHLCV；峰、半峰高上下界、均本、获利/套牢、窗口条数日期及标线，全部标为估算。
- 资金：完整原区域与字段；净额不能拆成流入流出，北向持仓不是流量；饼图只用真实互斥同口径完整分项，主力汇总不重复计入。
- 财务：PE-TTM/PB-MRQ/ROE/营收/净利/毛利率；股东姓名/比例/变动/国资；申万1/2级与行业PE/PB；事件摘要/类型/时间；宏观利率/通胀/汇率/商品/流动性的方向强度。缺失保留位置，不能以汇总伪装名单。
- 日/周/月/全部；分时、多日保持禁用。默认1Y日线、最近120条、MA模式六线均开启。五图十字线、滚轮缩放、平移、底部滑块、可见区价格轴；鼠标历史读数与筹码联动，离开回到可见区最右。宽屏原38px指标栏/自适应五图/242px筹码；窄屏筹码纵向保留。

## 公式和数据

对齐AF：BOLL样本标准差；MACD首值播种EMA；KDJ原RSV/递推；RSI简单滚动平均。MA完整窗口；BOLL20/KDJ9/RSI14次变化预热，MACD DIF第26/DEA柱第34条显示。周/月先聚合再重算全部指标。缺失不是0；平盘/零分母明确处理；涨跌幅振幅以前收为基准；均价仅真实字段或确认单位后计算。时间、复权、单位、报告期、TTM/MRQ严格保留。

ObservationRequest新增section_sources默认{}，逐区覆盖否则原source，禁止隐式回退；新增valuation区块复用market_snapshot，Wind的close/pe_ttm/pb/total_shares，同源同日才可派生市值。新UI显式行情tinysoft、估值wind、财务/资金/股东auto。新增section_ranges默认{}，只允许history/activity/margin完整ISO日期对；缺省保持旧全局日期。新UI明确行情1Y，资金/两融近60天（截止往前59天），Wind硬门不截断不拆分；刷新/恢复/快照回显有效来源和范围。holders.end_date仍是报告期，不参加历史区间映射。

ECharts5.5.0与Chart.js4.4.7本地静态资源已获用户独立授权，固定版本/许可/摘要并进入安装物，不依赖CDN。首轮接现有真实数据，缺数据保留全部原指标位，不新建行业/股东名单/宏观Provider。

## 分工合同

- 后端：asset_routes.py、asset_workspace.py及test_asset_workspace.py。
- 图表：asset-chart.mjs/css、新asset-indicators.mjs及相关JS测试。保留renderMarketTerminal(rows,state,metadata)、enrichMarketBars、createAssetChartController导出。controller提供configure(rows,key,metadata)、getState、mount(slot)、dispose、cancel、handle；内部更新图表/标签，不要求外层每次指针移动重绘DOM。
- 页面：asset-workspace.mjs/css、新asset-projection.mjs及页面JS测试；完整原区域，调用renderMarketTerminal；行情设置明确分区来源/日期。
- 主代理：app.mjs生命周期接线、vendor资源/安装CI、对照预览/E2E、文档与总体验证交付。

## 验收

原页与迁移页同一明确标注的测试输入对照截图；完整字段/交互清单；公式黄金值、预热/缺失/平盘/周月/筹码；实际AssetWorkspace→Broker→Provider的来源范围/60与61日/旧记录/刷新恢复；真实CJPY冷启动首次查询与逐区刷新；多宽度明暗、取消迟到响应/实例释放；离线库加载、wheel及Mac安装资源逐字节核对。最后独立Python/JS评审、完整Router与同候选Mac CI；先展示效果，常驻部署另行处理。
