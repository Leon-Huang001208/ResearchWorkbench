# Wind Style K-Line Panel Design

## Goal

资产分析页的 K 线区域改为接近 Wind 的高密度终端式布局，但不实现实时盘口、买卖队列或即时成交。

## Approved Direction

采用 Wind 终端式方案：

- 顶部不再显示 1月/3月/6月等截断范围按钮，K 线默认请求全量数据，但初始视窗只展示最近 120 根；工具栏保留 Wind 风格周期提示、日/周/月/全部切换和均线开关。
- 增加行情信息条，复用页面已有资产名称、代码、现价、涨跌、成交量、成交额、换手率。
- 左侧增加竖向指标导航，强化 Wind 风格的图表工作台结构。
- 主图和指标面板保持同一 ECharts 实例，调整为更紧凑的多面板比例；左侧竖向标签按真实图表分区对齐。
- MA 线支持 MA5、MA10、MA20、MA60、MA120、MA250；周 K、月 K 由前端基于全量日线聚合。
- 覆盖线采用互斥模式：右上角只保留 `MA均线`、`BOLL布林带`、`裸K` 三个模式按钮；MA 模式显示全部均线，BOLL 模式只显示 BOLL MID/UPPER/LOWER，裸K模式隐藏全部覆盖线。
- 主图左上角指标值跟随鼠标所在 K 线更新，并按对应 MA/BOLL 线条颜色显示；MA250 的线条、tooltip 和主图读数必须使用同一灰色配置。
- 成交量、MACD、KDJ、RSI 副图标题值也跟随鼠标所在 K 线同步更新，成交量 MA 按当前位置向前滚动计算。
- 缩放或拖动 K 线后，主图价格轴按当前可见 K 线和当前覆盖模式自动重算，避免蜡烛线或覆盖线超出价格区。
- 右侧筹码分布保持独立 ECharts 实例，但高度锁定到主 K 线价格区，不能延伸到成交量或指标区；筹码图使用连续价格轴，并与主 K 线主图共享 y 轴 min/max，使现价和边界线与左侧价格位置对齐。
- 筹码峰、筹码峰上界、筹码峰下界、现价、均本都在筹码图中以 markLine 显示，并在统计区显示对应数值；筹码图按当前可见区间起点到当前激活 K 线动态重算普通筹码/成交量价格分布。dataZoom 缩放或拖动会改变区间起点和默认右端，鼠标悬浮会改变区间右端，鼠标移出后回到当前可见 K 线图最右侧交易日。

## Scope

Only `app/web` changes:

- `app/web/templates/index.html`
- `app/web/static/style.css`
- `app/web/static/js/asset.js`

No backend contracts or API changes are required because `chip_peak_upper` and `chip_peak_lower` already exist in the asset analysis payload.

## Verification

- Browser-load the Web Workbench.
- Open asset analysis and render a stock with K-line data.
- Confirm the K-line region uses terminal layout.
- Confirm chip peak upper and lower boundary labels are visible in the chip distribution chart and stats.
