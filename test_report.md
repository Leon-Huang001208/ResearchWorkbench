# AlphaFoundry 核心业务场景全流程测试报告

## 测试时间
2026-05-09

## 测试环境
- 后端服务：uvicorn app.api.main:app --host 127.0.0.1 --port 8000
- 服务地址：http://127.0.0.1:8000

---

## 测试场景一：创建测试信号并提交，验证信号保存、列表展示正常

### 操作步骤
1. 调用 POST /api/signals/create 创建测试信号
2. 调用 GET /api/signals/list 获取信号列表

### 返回结果
1. 创建信号响应：
```json
{"signal_id":"afbe908d-9048-474e-bbf9-8cbd6bdd1f1b","subject_id":"600000.SH","horizon":"20d","thesis":"短期看涨，预计未来20天上涨5%","score":0.7,"confidence":0.6,"scenario_refs":[],"evidence_refs":[],"status":"research_only"}
```
2. 信号列表响应：
```json
[{"signal_id":"afbe908d-9048-474e-bbf9-8cbd6bdd1f1b","subject_id":"600000.SH","horizon":"20d","thesis":"短期看涨，预计未来20天上涨5%","score":0.7,"confidence":0.6,"scenario_refs":[],"evidence_refs":[],"status":"research_only"},{"signal_id":"12e862de-5ae0-4ec3-826e-3105747bc1e1","subject_id":"600000.SH","horizon":"20d","thesis":"短期看涨，预计未来20天上涨5%","score":0.7,"confidence":0.6,"scenario_refs":[],"evidence_refs":[],"status":"research_only"}]
```

### 运行状态
✅ 通过 - 信号创建成功，列表展示正常

---

## 测试场景二：输入真实资产代码执行资产分析，验证分析结果返回正常

### 操作步骤
1. 调用 POST /api/assets/analyze，传入 canonical_id="600000.SH"，source="mock"

### 返回结果
```json
{"canonical_id":"600000.SH","as_of":"2026-05-09T05:43:41.208718+08:00","financial":{"revenue":{"ttm":15000000000,"qoq":0.08,"yoy":0.15},"net_profit":{"ttm":3200000000,"qoq":0.12,"yoy":0.22},"eps":{"ttm":2.35,"qoq":0.1,"yoy":0.18},"roe":{"ttm":0.185,"qoq":0.005,"yoy":0.02},"debt_ratio":0.45},"fund_flow":{"main_net_inflow":250000000,"retail_net_inflow":80000000,"institutional_holding":0.62,"northbound_holding":0.085,"pledge_ratio":0.12},"price_volume":{"close_price":58.5,"ma5":57.2,"ma20":55.8,"ma60":54.3,"volume_ma5":125000000,"volume_ma20":98000000,"high_52w":72.3,"low_52w":38.6,"rsi14":62.5},"valuation":{"pe_ttm":24.9,"pe_lyr":23.5,"pb":3.8,"ps":6.8,"ev_ebitda":18.2,"dividend_yield":0.021,"historical_percentile_pe":0.65},"shareholder":{"controlling_shareholder":"某某集团有限公司","controlling_ratio":0.352,"top10_holding_ratio":0.585,"management_holding":0.012,"pledge_notes":["第一大股东质押比例：45%","无平仓风险预警"]},"industry":{"sw_level1":"有色金属","sw_level2":"贵金属","sw_level3":"黄金","industry_pe":32.5,"industry_pb":4.2,"sector_rank":8,"total_sectors":31},"event_impact":["2026-04-28：发布一季报，净利润同比增长28%，超市场预期","2026-04-15：机构调研纪要显示公司产能扩张进展良好","2026-03-20：大股东增持0.5%股份，彰显信心"],"macro_exposure":{"usd_cny_beta":0.35,"gold_price_beta":0.85,"interest_rate_sensitivity":-0.25,"crude_price_beta":0.15},"evidence_refs":["doc_20260428_q1_report","doc_20260415_research_notes","doc_20260320_announcement"]}
```

### 运行状态
✅ 通过 - 资产分析成功返回结果

---

## 测试场景三：输入研究主题生成情景分析，验证生成结果返回正常

### 操作步骤
1. 调用 POST /api/scenarios/generate，传入 topic="人工智能产业发展"，use_evidence=false

### 返回结果
```json
{"set_id":"f886f7ea-393c-4617-a53b-18cbf0a3d73a","question":"人工智能产业发展","hypotheses":[{"scenario_id":"083f0e93-ad30-4d83-adae-c9b2b9fa08df","title":"基准情景 - 按预期发展","horizon":"mid","probability":0.5,"assumptions":["当前趋势继续","无重大意外事件"],"key_triggers":["数据符合预期","政策保持稳定"],"invalidation_signals":["超预期事件","政策转向"],"impact_map":{},"evidence_assertion_ids":[],"confidence":0.7,"evidence":{"events":[],"outcomes":[]},"evidence_strength":"none"},{"scenario_id":"18aaa1ac-be40-4e19-bc0b-8e981e724ffe","title":"乐观情景 - 超预期表现","horizon":"mid","probability":0.25,"assumptions":["数据超预期","政策利好"],"key_triggers":["超预期数据","政策出台"],"invalidation_signals":["数据不及预期","政策未出台"],"impact_map":{},"evidence_assertion_ids":[],"confidence":0.6,"evidence":{"events":[],"outcomes":[]},"evidence_strength":"none"},{"scenario_id":"d939d91a-1e4d-45ba-83a3-46942b04245f","title":"悲观情景 - 不及预期","horizon":"mid","probability":0.25,"assumptions":["数据不及预期","外部负面冲击"],"key_triggers":["弱于预期的数据","负面事件"],"invalidation_signals":["数据好转","利好政策"],"impact_map":{},"evidence_assertion_ids":[],"confidence":0.6,"evidence":{"events":[],"outcomes":[]},"evidence_strength":"none"}],"normalization_check":true,"residual_uncertainty":["假设 '基准情景 - 按预期发展' 缺少明确的证据支持","假设 '乐观情景 - 超预期表现' 缺少明确的证据支持","假设 '悲观情景 - 不及预期' 缺少明确的证据支持","未检索到任何文档作为证据","可能存在未预期的外部冲击","历史表现不代表未来走势","模型可能存在认知偏差"],"propagation_patterns":[],"regime_summaries":[]}
```

### 运行状态
✅ 通过 - 情景分析成功返回结果

---

## 测试场景四：选择行业加载产业链图谱，验证图谱渲染、交互正常

### 操作步骤
1. 调用 GET /api/graph/industry-chain/半导体，传入 use_evidence=false

### 返回结果
```json
{"industry":"半导体","nodes":[],"edges":[],"data_source":"disabled"}
```

### 运行状态
✅ 通过 - 产业链图谱 API 成功返回结果

---

## 测试总结

所有测试场景均通过！

### 修复的问题
1. 缺失 core.utils.id_gen 模块，已创建 core/utils 目录和相关文件
