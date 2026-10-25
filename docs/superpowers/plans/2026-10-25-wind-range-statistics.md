# Wind Range Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development; implement and review each task before integration.

**Goal:** 在现有资产图表加入右键拖选的单区间统计，保持原有数据、日期、筹码和视区交互。

**Architecture:** 独立纯计算模块处理已取得的同版本日线；独立 DOM 控制器管理选框和单浮窗。asset-chart 只转接真实坐标和生命周期；不引入服务、依赖或第二种数据源。

**Tech Stack:** 原生 JavaScript ESM、现有 ECharts 5.5.0、Node test，原安装/CI链。

---

### Task 1: 纯计算合同
Files: create `app/research_web/ui/asset-range-statistics.mjs`, `tests/javascript/research_web_asset_range.test.mjs`.

- [ ] 写RED测试，导入 `calculateRangeStatistics(daily,{startDate,endDate},metadata)`；返回实际range及metrics，每项含value/unit/status/reason/definition，保留零、缺失和原输入。
- [ ] 使用Node24 `node --test tests/javascript/research_web_asset_range.test.mjs` 记录真实失败。
- [ ] 实现闭合公式，涨跌/振幅用前收，250日复利年化；极值高低计算截图口径的回撤/上涨并标注。行业无基准保持未取得。量额/换手有缺失则不完整汇总。
- [ ] 验证截图463.15/393/501.26/337.10和32日，与-15.15/-72.28/-32.75/48.70/35.44相符；日周月映射、反向/单日/零、单位/缺口、前收和复权基础负例。
- [ ] 运行目标测试并自查；先spec review再JS quality review。由主会话提交任务改动。

### Task 2: 真实手势及浮窗
Files: create `app/research_web/ui/asset-range-controller.mjs`; modify `asset-chart.mjs`, `asset-chart.css`, `asset-workspace.mjs`; tests in `research_web_asset_range_controller.test.mjs` and existing chart/workspace tests.

- [ ] 先写事件与状态测试：右键和左键区分、反向拖选、坐标裁剪、空点击、取消/失焦、只在主图生效。
- [ ] 控制器接口 `createRangeController({host,getContext,logger})` 返回begin/move/end/open/clear/render/dispose；context含daily、displayBars、metadata及主绘图区像素/日期映射。不直接修改图表state或筹码。
- [ ] 单浮窗两列统计与起止日期输入，标题可拖动，边界受容器限制，Esc与关闭清除。窄屏置图下；更多菜单中提供区间统计入口，控件可键盘操作。
- [ ] asset-chart在真实事件入口区分右键，阻断本次左pan与日期更新；只在已取得范围内计算，不触发额外供应商取数。版本/资产变更、dispose清理监听器与旧计算，周期变化保留日历区间。
- [ ] 测试周月选择映射源日线、关闭/拖窗不改视区或筹码截止日、原图表回归；审查后提交。

### Task 3: 集成、交付和真实效果
Files: docs/research-web-ui.md, docs/research-web-appearance.md, docs/DEVELOPMENT_MAP.md, related module docs, `.ai/reports/2026-10-25-wind-range-statistics.md`; existing Bootstrap asset list when required.

- [ ] 核对requirements/web.in、web.lock、setup_web.py、installation与Bootstrap，新静态资源进入安装产物并字节一致；不安装依赖。
- [ ] 独立隔离快照预览，实际右键拖选/编辑/关闭、月K、筹码、页签、明暗宽窄；截图及公式单测分别取证。
- [ ] 完整JS与Router、独立最终评审、原Constraints/Checks/同候选Mac Bootstrap；保留未执行平台状态。
- [ ] 走受管PR及合并；常驻切换需独立固定候选与原空闲/三锁/保全门。活动未知时不部署，保留真实原因。登录实页验收与资源安全收尾另记证据。
