# CPU 有界投研 Skill 阶段 2 实施报告

## 范围

本阶段在阶段 1 `cpu_bounded_v1` 底座上新增六个仓库内置、独立、单一职责 Skill：每日市场简报、
政策哨兵、事件复盘、ETF 资金流、业绩报告监控与业绩预告监控。每个包都有重写后的 `SKILL.md`、
受审 `scripts/calculate.py`、输入/输出 schema、DataHub/Wind 字段映射、来源 provenance、synthetic
fixture 和 golden result。能力中心通过既有种子、检查和不可变版本链注册这六项，未新增
Workflow、页面、顶层 API、执行器或依赖，也未改变已有 slug。

## 计算与证据边界

- 六个脚本只接受相对路径 JSON；先应用共享工作量预算，累计最多 50,000 行/64 MiB，不截断输入。
- 输出统一包含 `skill_slug`、`method_version`、`compute_profile=cpu_bounded_v1`、`as_of`、
  `parameters`、`dataset_refs`、`status`、`metrics`/`rows`、`limitations` 与
  `research_only=true`，并保留输入 provenance。
- 每日市场简报只编排已提供的市场、涨跌/成交、行业/主题和新闻证据，不承担事件或政策归因。
- 政策哨兵只形成证据时间线、关键词/日期命中和输入给定的潜在影响对象，不生成投资建议；无证据
  失败关闭。
- 事件复盘确定性计算事件窗收益、相对基准超额和成交变化；回归观测不足时 beta/alpha 返回
  `unavailable`/空值及 limitation，不使用 beta=1 默认值。
- ETF 资金流按份额变化与 NAV/价格计算，只按用户提供的类型、行业、主题汇总；分类缺失失败。
- 两类业绩监控分别计算披露进度/同比环比分布和预告利润中值/增速分布；必填字段缺失失败，可选的
  市值、估值、基金/北向暴露和研究覆盖只透明汇总，不推断。
- `field-mapping.json` 逐项声明 DataHub 业务工具、Wind 首选字段、单位、日期、复权与允许等价字段；
  阶段 1 Wind provider 不支持的 ETF 份额、宏观、基金/北向暴露或研究覆盖标为
  `data_not_equivalent`，必须经过已验证的其他来源或用户输入 fallback gate。
- 种子构建把共享 CPU 预算模块、预算说明、结果协议和 provenance 协议复制到每个不可变版本，
  并由现有机制生成/校验每个 Python 资源的 reviewed script SHA-256。

## 规格审查整改

- 六个输入 schema 与运行时计算器统一要求 `data_contract`，逐项验证 provider、mapping ID/version、
  单位、日期语义与复权方式；不匹配稳定返回 `data_not_equivalent`。根、parameters、dataset ref、
  每条记录及 ETF classification 都拒绝未知字段。
- 结果 `as_of` 成为严格的前视边界：dataset ref、市场/交易日、政策发布日期、报告期和披露日均不得
  晚于它，未来数据稳定返回 `future_data`。
- `workload_too_large` 的 CLI JSON 保留安全的 resource、limit、actual 和 `reduce_scope=true`，不回显
  输入内容。共享 `input_contract.py` 与预算脚本一并复制到不可变版本并进入 reviewed script 哈希。
- 六项真实 Wind/Excel 对照尚未执行，因此种子初始状态改为 disabled；能力中心仍可发现并检查，
  但选择执行返回 `capability_disabled`。只有取得并登记成功的 macOS Wind 对照 receipt 后才可启用，
  synthetic golden 不替代该证据。
- 每项均增加近声明上限的独立进程压力用例；父测试进程轮询目标进程 peak RSS，断言运行小于 10 秒、
  peak RSS 小于 1 GiB，输入文件小于 8 MiB，数据生成确定且不依赖网络或原始工作簿。

## TDD 与验证

严格 TDD 的首轮 RED 为 `20 failed, 1 passed`：六个包、脚本、种子和资源尚不存在；实现后 Stage 2
专项先达到 `21 passed in 2.52s`。继续先补严格 envelope/dataset ref 与 CLI 契约，得到六个预期
unknown-field RED；同时发现 `capsys` 与项目 pytest-asyncio 配置的六个夹具错误，改用标准库输出捕获
后不再依赖该夹具。最终专项为 `33 passed in 2.85s`，能力相关 Python 回归为
`134 passed, 1 warning in 105.59s`；能力包、admission、native、review、safety、研报包和本阶段
测试的完整相关回归为 `225 passed, 2 skipped, 1 warning in 189.80s`，Node 能力中心回归为
`34 passed`。两个跳过项均为测试声明的外部 DSH 条件，warning 是 Starlette/anyio 第三方弃用提示。
每个 synthetic golden 的
日期、状态、信号和分类逐项精确比较，浮点使用
`rtol=1e-6`、`atol=1e-8`；每个常规 fixture 均断言小于 2 秒。失败用例覆盖缺失、错误类型、空值、
预算超限、事件 beta 样本不足、ETF 分类缺失、两类业绩必填字段缺失、政策证据缺失和简报无数据。
静态扫描拒绝 GPU 框架/CUDA/MPS/Metal、CJPY、外部 CDN、绝对路径、VBA、网络、子进程和线程池。

规格审查整改同样先写失败测试：首轮为 `26 failed, 31 passed in 2.32s`，覆盖 disabled 种子、严格
schema/运行时等价性、未来数据、嵌套未知字段和六个 CLI 超限 metadata；实现及六个独立进程压力
用例完成后，Stage 2 专项为 `63 passed in 2.54s`。该时间包含 4,800 行市场/政策/双序列样本及
48 标的 ETF/业绩样本的六个子进程检查，每项均实际满足 `<10s` 与 `<1GiB peak RSS` 断言。

- 目标 Python 文件 `ruff check`、`black --check`、`isort --check-only` 通过；七个生产 Python 目标
  分别执行 `mypy --follow-imports=skip`，均无问题。
- `node --test tests/javascript/research_web_capabilities_ui.test.mjs`：34 passed；
  `node --check app/research_web/ui/capabilities.mjs`：通过。
- `node scripts/check_research_architecture.mjs --project .` 与
  `python scripts/check_doc_sync.py --project .`：`violations: []`；首次运行按规则要求补充 Tabbit
  非影响说明与架构 review receipt 后复跑通过。
- `.agents/project-constraints.mjs` 对 Git 枚举的 67 个变更文件检查为零违规；
  `python scripts/check_task_completion.py`、重建 `docs/generated/py_file_index.md` 与 JSON schema
  解析检查通过。
- 对三个只读来源 Skill、三个来源脚本和三个未执行 Excel 工作簿运行 SHA-256 核对，九项均与包内
  provenance/任务给定值一致；未读取工作簿内容，也未启动 Excel 或 VBA。

整改收口再次执行 Stage 2 专项为 `63 passed in 12.62s`（与其他短门并行时的套件总时长；六项
独立进程各自仍满足 `<10s`）；Stage 2、CPU budget 与 disabled 会话快照聚焦组合为
`73 passed, 1 warning in 3.84s`。能力中心 Node 回归为 `34 passed`；目标 ruff、black、isort、mypy、
JSON 解析、`check_research_architecture`、doc-sync、project constraints、task completion 与
`git diff --check` 均通过。未重复 105 秒和 189 秒级全回归；其结果仅保留为本报告前述首轮证据。
最后一处 policy 嵌套影响对象校验调整后，仅复跑对应短测，结果为
`10 passed, 53 deselected in 9.95s`；随后对最终 12 个 Python 变更目标复跑 ruff、black 与 isort，
并对包含未跟踪共享契约文件在内的 50 个最终变更文件复跑 project constraints，均通过。

不会把未执行的平台或真实数据验证写成已通过。

## 未验证项

本阶段未调用真实 Wind、网络或原始 Excel/VBA，三个 Excel 模板与三个外部 Skill 仅作只读来源和
哈希证据；未验证真实 Provider 数据质量、厂商字段可用性、Windows 原生沙箱或 Excel 运行。Web-only
代码未修改任何桌面专属路径，不能由本地离线测试推导桌面或跨平台交付结论。六项能力因此保持
disabled；需要真实 macOS Wind 对照 receipt 才能进入启用验收。
