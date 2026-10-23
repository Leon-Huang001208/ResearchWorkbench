# ETF 经济字段 Host 原件核对

宿主：macOS；任务：Web 功能修复；范围：Host 冻结原件重放和离线验收。

## 根因与修复

原 Host 只核对经济事件日期、国家、指标、重要性是否存在及范围，没有用同 Run 原件重建字段。
本轮在既有 assess 入口加入真实 Excel collection policy／require flag 专属门：
加载 manifest 不可变来源合同，运行时调用现有只读 read_exports 校验冻结工作簿、coverage 和
原生观察 receipt，再由 Host 独立构建九字段事件。顺序、日期、source_sheet、国家、指标、冻结
重要性映射及四个可选字段连同来源绑定采用规范 JSON 精确比较，区分 int/float/bool。
空列、None、空字符串归一 None；保留其他 str/int/有限 float；bool/非有限值/容器拒绝。
日志只记错误类型，稳定 blocking code 为 weekly_excel_economic_replay_unverified。

API 与无实采标签的 legacy Excel fixture 沿旧合同，所有旧硬门继续执行。Word 三列表未修改。
仅修改 weekly_sources.py、weekly_data.py、新经济字段测试及生产文档；无新依赖、Git写入、
Office、厂商、模型或网络调用。没有修改原始实采封包或历史快照。

## TDD 与验证

测试复用原 package/receipt/source helper，生成并冻结真实本地双 sheet xlsx；财经页只有五列。
第一次 RED 夹具未给 series/calendar 配套 retrieved_at，不能作为有效旧行为证据，明确保留日志
logs/etf-excel/economic-host-red.log，不据此认证。
修正夹具后，在测试进程只将新增 verify_weekly_economic_export 置为 no-op 重放旧 Host 逻辑：
logs/etf-excel/economic-host-red-reproduced.log：28 failed、4 passed，包含旧 Host 将字段篡改、
字段/事件遗漏、插入、重排序、缺上下文和原件 bool 当作 0 等错误输入放过的失败断言。
新实现及既有 weekly_data/gold_supplement 近测：logs/etf-excel/economic-host-green-near.log，
114 passed（22.20s）。32 项新测试覆盖四可选字段、其余事件身份、严格数值类型、缺上下文／
合同资源／哈希变化、原件变化、原件 bool 拒绝、缺财经列 None、require flag 及非有限输入。

测试解释器使用已批准主 .venv，PYTHONPATH 使用 feature devtools site-packages，并注入 fake
xlwings，pytest --noconftest -q -o addopts=；未安装依赖。
Ruff／Black／isort 为三个所属 Python 文件的 scoped 检查。scoped mypy --follow-imports=silent
检查两个源码文件：logs/etf-excel/economic-host-mypy.log，Success: no issues found in 2 source files。
最终组合回归与提交／CI 由主任务统一绑定最终候选；本报告不宣称 CI、实采、模型或正式成稿通过。
