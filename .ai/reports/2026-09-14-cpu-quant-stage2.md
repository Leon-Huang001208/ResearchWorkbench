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

第二轮规格复审继续先写失败测试：新增日期、来源哈希、CNY 口径、daily 必填集合/市场宽度及
跨平台压力测试约束后，聚焦 RED 为 `17 failed, 62 deselected in 0.34s`。共享输入契约随后把日期
固定为扩展格式 `YYYY-MM-DD`，统一验证六项 `source_hashes`；缺失哈希时保留空映射、添加
`source_hashes_missing` 并把结果降级为 partial。daily 的运行时必填集合与 schema 对齐，breadth
只接受非负整数；daily/ETF 的 currency 固定 CNY。clean catalog 的非 DSH 测试进一步证明六个
disabled slug 不进入 native provider candidate 目录。

新增行为首轮 GREEN 为 `18 passed, 64 deselected in 1.33s`；Stage 2 与 native 聚焦回归为
`80 passed, 2 skipped in 3.23s`，两个 skip 仅是仍需 `DSH_SOURCE_ROOT` 的固定上游 provider/tool
源码集成，而 clean catalog candidate 断言不依赖该环境且实际执行通过。压力测试改用项目已有
psutil 7.2.2 从父进程采样 RSS 并处理退出竞态，不安装依赖、不调用系统 `ps`；六项复跑为
`6 passed, 73 deselected in 0.72s`，最大单项耗时 `0.08903s`、最大 peak RSS
`28,049,408 bytes`，均来自 policy-sentinel。
最终对九个 Python 变更目标执行 ruff、black、isort，对七个生产目标逐项执行 mypy，结果均通过；
包/schema 聚焦检查 `3 passed, 76 deselected in 1.49s`。`check_research_architecture`、doc-sync、
project constraints、task completion 与 `git diff --check` 均通过；未重复长回归。

最终 Important 复审同样先写失败测试：六个计算器分别覆盖 `source_hashes` 显式 null、空白 key、
`" source "` 与 `"source"` 的 trim 碰撞，并统一断言六份 input schema 的 `propertyNames`。RED 为
`7 failed, 73 deselected in 0.29s`。共享校验现在仅把字段缺失视为可披露降级；显式 null、非规范或
空白 key 稳定返回 `invalid_source_hashes`，也不再静默 trim key。首轮 GREEN 为
`7 passed, 73 deselected in 0.14s`；同步 schema 和包资源后的聚焦复跑为
`8 passed, 72 deselected in 0.26s`。八个本轮 Python 目标通过 ruff、black、isort；七个生产目标逐项
通过 `mypy --follow-imports=skip`。六份 input schema 解析、`check_research_architecture`、doc-sync、
project constraints（28 个最终变更文件）、task completion 与 `git diff --check` 均通过。本轮只执行
聚焦短测，没有重复 Stage 2 或能力全回归。

最终 schema/运行时一致性复审先加入六计算器的 CR、LF、U+2028、U+2029 key 反例，并用
Draft 2020-12 validator 直接验证六份 `propertyNames` 行为；RED 为
`7 failed, 73 deselected in 0.42s`。共享 validator 与统一 schema pattern 随后明确拒绝四类换行
分隔符，普通内部空格仍允许；GREEN 为 `7 passed, 73 deselected in 0.29s`，资源完整性组合复跑为
`8 passed, 72 deselected in 0.33s`。本轮两个 Python 目标通过 ruff、black、isort，共享生产目标通过
mypy；六份 schema 解析、架构、doc-sync、project constraints（22 个变更文件）、task completion 与
`git diff --check` 均通过。本轮继续只运行聚焦短门。

质量审查整改首先增加六类 RED：持久 comparison receipt/旧版迁移、数值转换和派生有限性、真实
sandbox 输出门、业绩预告报告期等价、相对 JSON 链接防护及每日简报 provenance 规范化。首轮为
`54 failed, 74 deselected in 25.51s`，其中 receipt/迁移 18 项、数值 15 项、sandbox 6 项、报告期
1 项、安全输入 13 项和 dataset refs 1 项。实现遵循 catalog 现有原子 JSON 存储，没有新增顶层 API；
只有这六个 slug 的启用和回滚到 enabled 会校验绑定 slug、不可变版本、`calculate.py` SHA-256、
UTC 时间、macOS、`wind_excel`、passed 结果和证据 SHA-256 的持久 receipt。已知初版脚本哈希升级时
发布当前版本并保持 disabled，不继承旧启用状态。该子组首轮 GREEN 为
`18 passed, 110 deselected in 25.96s`。

六 CLI 随后统一使用共享相对 JSON 安全 loader：规范化后必须仍在 cwd 内，逐级拒绝符号链接或
reparse point，并在 no-follow 打开前后核对普通文件身份；六项文件/目录链接反例均稳定拒绝。共享
受检数值原语覆盖输入 float 转换、加减乘除/求和/均值和全部派生指标，溢出或非有限值统一为
`invalid_number`，最终 JSON 序列化固定 `allow_nan=false`。该数值、安全输入、错期预告与 daily
规范 refs 组合为 `30 passed, 98 deselected in 1.12s`。

近上限用例不再直接运行计算器，而是通过真实 `sandbox.py` supervisor、Seatbelt 和 64 KiB
`max_output` 门；每项完整处理 4,800/9,600/48 行，输出只内联至多 128 条并通过 `row_delivery`
披露省略计数及规范化 dataset refs。六项为 `6 passed, 122 deselected in 1.37s`，最大单项 wall
`0.206s`，最大父子进程 RSS 合计 `45,826,048 bytes`，stdout 均小于 64 KiB。更新后的六份 golden
和输出 schema 直接校验为 `6 passed, 122 deselected in 0.38s`。
最终未重复能力全回归：除已单独通过的 receipt/迁移用例外，其余 Stage 2 短测为
`116 passed, 12 deselected in 13.33s`。十个 Python 目标通过 ruff、black、isort，八个生产目标
逐项通过 mypy；六包 JSON、architecture、doc-sync、project constraints（46 个变更文件）、task
completion 与 `git diff --check` 均通过。

最终质量复验继续以 TDD 收紧四处边界。首轮四组为 `28 failed, 116 deselected in 26.81s`；其中
27 项是 receipt artifact、迁移、封套/集合和 ancestor race 的产品 RED，另 1 项是测试漏导入
`WorkloadBudget`，修正夹具后再进入实现。comparison receipt 登记现在只接受位于 catalog 数据根的
严格 evidence artifact 路径，读取脱敏绑定字段并重算 artifact、输入来源、不可变版本内仓库 golden、
实际结果与当前计算脚本摘要；持久 receipt 由 verifier 派生，enable/rollback 会重新读取 artifact，
文件缺失或摘要/绑定变化即失败关闭。该设计消除了调用方直接提交 `passed` 字典或自填摘要的路径，
但不宣称能够抵抗拥有本机写权限的管理员主动伪造整套文件。

已知初版迁移在构造新版本前先撤下原生投影、把状态持久为 disabled；publish/save/validation 异常
保留 disabled/uncertain 或使 catalog 初始化失败，不再恢复旧 enabled 投影。共享 loader 在 POSIX
从 cwd 目录描述符开始，以 `dir_fd`、`O_DIRECTORY`、`O_NOFOLLOW` 逐组件打开并通过 `fstat` 验证，
最终文件也从可信父目录 fd 打开；Windows 路径以打开句柄的最终路径和 reparse 状态复核，无法确认
时失败关闭。ancestor 目录切换 race、文件/目录 symlink 和 cwd containment 均有稳定反例。

输出边界增加 `dataset_refs`/`source_hashes` 各 32 项、复制文本 4096 字符和完整 strict JSON envelope
64 KiB UTF-8 限制；超过任一边界返回小型、完整的 `workload_too_large`/`reduce_scope` 错误。
`row_delivery` 只声明复用规范化顶层 refs，不再第三次复制 refs。300 refs 与长文本用例通过真实
sandbox 64 KiB gate；六项近上限压力样本全部计算，最大 wall `0.248s`、父子进程峰值 RSS
`45,416,448 bytes`。四组首次 GREEN 后 Stage 2 专项为 `144 passed in 39.97s`；后续只运行新增
envelope/evidence 反例和必要短门，不再重复该 40 秒套件。文档同步后的高风险选择性回归为
`24 passed, 121 deselected in 27.10s`，相关 native catalog 回归为 `1 passed, 2 skipped in 1.97s`。
九个 Python 目标通过 ruff、black、isort，catalog 与共享契约以 `--follow-imports=skip` 通过 mypy；
36 份 Stage 2 JSON 解析、架构、doc-sync、project constraints 和 `git diff --check` 均通过。

不会把未执行的平台或真实数据验证写成已通过。

## 未验证项

本阶段未调用真实 Wind、网络或原始 Excel/VBA，三个 Excel 模板与三个外部 Skill 仅作只读来源和
哈希证据；未验证真实 Provider 数据质量、厂商字段可用性、Windows 原生沙箱或 Excel 运行。Web-only
代码未修改任何桌面专属路径，不能由本地离线测试推导桌面或跨平台交付结论。六项能力因此保持
disabled；需要真实 macOS Wind/Excel comparison evidence artifact 经内部 verifier 生成 receipt 才能
进入启用验收。仓库测试使用 synthetic golden/result 副本，仅验证门禁机制，不是实测 receipt。
