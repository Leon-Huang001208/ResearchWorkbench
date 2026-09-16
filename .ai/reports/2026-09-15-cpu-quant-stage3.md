# CPU 有界投研 Skill 阶段 3 实施报告

## 范围

本阶段在既有 `cpu_bounded_v1` 共享契约上新增七个仓库内置、独立、单一职责 Skill：基金匹配、基金
穿透、组合重合度、组合基准偏离、行业景气度、行业象限监控和行业拥挤度监控。每个包均包含受审的
`SKILL.md`、`scripts/calculate.py`、严格输入/输出 schema、DataHub/Wind 字段映射、来源
provenance、可哈希 synthetic source artifact、fixture 与 golden result。能力中心通过既有种子、不可变
版本与 comparison receipt 门控登记七项；未新增 Workflow、页面、顶层 API、依赖或 Stage 4 内容。

## 计算与证据边界

- 基金匹配只对输入给定的风格、风险和业绩特征计算归一化加权 L1 距离；不抓取基金数据，也不生成
  买卖建议。
- 基金穿透统一接受 percent/decimal 权重，支持多层基金持仓和重复路径聚合；对全部给定基金子图做
  拓扑环检测（包括根基金不可达的子图），发现 cycle 即失败关闭；合法汇合 DAG 按深度动态聚合到达
  权重、路径数和日期，不按路径指数递归。所有边必须来自同一完整快照，混合
  日期返回 `data_not_equivalent`；每 owner 1,000 行上限在重复边聚合前按原始受理行计数。
- 组合重合度与组合基准偏离都只接受单一快照，转换后每行权重限定 `(0, 1]` 且每侧合计不超过 1，
  不把杠杆隐式归一化。基准偏离另要求每条记录显式携带并严格匹配顶层报告期、因子日与行业映射
  版本；同一 canonical `asset_id` 跨组合/基准的行业和因子事实也必须一致。因子日期必须等于持仓快照；
  混合值返回 `data_not_equivalent`。
- 三个行业 Skill 只接受调用方预聚合的行业指标：景气度计算方向调整的加权百分比变化，象限监控按
  给定水平和动量阈值分类，拥挤度监控计算行业成交额占全市场成交额的滚动比例及历史经验分位；均
  不读取个股明细或自行聚合原始行情。景气度的嵌套指标贡献在完整计算后全局最多投影 128 条；拥挤
  度要求所有行业共享完全相同的规范交易日序列与最新日期，每行业至少提供 `rolling_days + 1` 条原始
  观测以形成至少两个滚动值，且每日互斥行业成交额合计不超过市场总额。
- 当前项目 DataHub 工具没有七项计算所需的完整已核验联合字段口径，`field-mapping.json` 明确标记
  `callable=false`，运行时只接受 synthetic/user_input；`data_contract.provider` 必须与每个
  `dataset_ref.provider_id` 一致，否则失败关闭。
- 七个脚本的 schema 与运行时逐层字段等价：根对象、parameters、dataset ref、每条记录和输出封套
  均拒绝未知字段；严格校验扩展格式 `YYYY-MM-DD`、前视日期、有限数值和受检算术。
- 输入只允许 cwd 内相对 JSON，并复用逐组件 no-follow/句柄复核的安全 loader；不得通过绝对路径、
  `..`、符号链接或 reparse point 逃逸。
- `cpu_bounded_v1` 预算固定为最多 50,000 行、64 MiB 输入、单序列 5,000 点、最多 50 条序列且每条
  1,000 点。完整 strict JSON envelope 不得超过 65,536 UTF-8 bytes，成功 stdout 不附尾随换行；
  超限稳定返回 `workload_too_large` 和 `reduce_scope=true`。
- 静态与运行边界禁止 GPU/CUDA/MPS/Metal、网络、VBA、CJPY、绝对产品路径及隐式数据获取。

## 能力状态与来源

七项在 clean catalog 中可发现、可检查，但初始及迁移状态全部为 disabled。comparison evidence 升级
为 schema v2：除当前 slug、不可变版本、脚本摘要、仓库 golden、实际结果与来源摘要外，还分别绑定
仓库 synthetic input artifact、独立 Wind/Excel actual input artifact，以及固定宿主执行器身份和可执行
文件摘要。catalog 只接受由宿主侧 `RESEARCH_COMPARISON_REGISTRAR_KEY` 产生的 HMAC-SHA256 签名；
research sandbox 使用显式最小环境，不继承此密钥。缺少登记器、普通 JSON 自报、签名篡改或任一绑定
制品变化均失败关闭。测试用独立重编码结果模拟登记器协议，不调用被审 `calculate.py` 生成 actual 后
启用。启动时 catalog 逐项复核所有已启用的 receipt-gated 能力，非 v2、HMAC/证据不可复核或缺少
登记密钥时撤下投影并持久化 disabled；selection 也执行同一防御性门禁。catalog 以七个初始 Stage 3
脚本及两个已发布直接父版本的精确 SHA-256 白名单识别已安装旧版本，先撤下旧原生投影并禁用，再
发布当前不可变 successor；receipt 绑定旧版本，不能被新版本复用。直接父提交
`4647589c53e3aca75b9310f6600eac081d0599fa` 中基金穿透与组合基准偏离脚本的摘要分别经
`git show <commit>:<path> | shasum -a 256` 逐字计算为
`d9721c43c5e89ebe43bed8a0e4da47ad86c663d319794b09f1839a33b0d913c7` 与
`13dbeb59c8240c6eabcd79acf857291b9781d30382eff56a75df0c1801133d16`；原始旧摘要继续兼容，不接受
任何未列举摘要。真实 Wind/Excel 尚未执行，因此七项仍 disabled。

本阶段只把能够逐字核验的来源写入 provenance：

- 七个 `fixtures/source-artifact.json` 是仓库提交的 synthetic 输入制品；fixture、golden、provenance
  均绑定其实际 SHA-256，不再使用 `111…`/`aaaa…` 等占位摘要。它们仅证明离线确定性，不是真实来源。

- 组合基准偏离工作簿 SHA-256：
  `415d61e46b2c390de928c0f33011792d94f70efb508e59176d7aa77168c6c504`。
- 组合基准偏离 synthetic source artifact 增加逐条报告期、因子日、行业映射版本及跨 book canonical
  资产事实后的 SHA-256：`c5ef76a518b567ffa654235fe445e17f1ac6c5b2ec0406d23edd4b8b3baf9b1a`。
- 行业拥挤度工作簿 SHA-256：
  `24010fb2dd76604442d89b7ea4c3c691e3cdc198c87bd191ed1aaf020a0bb831`。
- 基金匹配、基金穿透、组合重合度、行业景气度和行业象限监控的原始 Skill/script 在已检查的来源
  位置不可用；对应 provenance 明确记录 `source unavailable`，不猜测 SHA-256，并保持 disabled。

## TDD 与验证

首次提交前中断恢复时 Stage 3 专项为 `68 passed, 1 failed`，唯一失败是测试从能力列表摘要读取不存在的
`versions` 字段。列表继续只验证摘要契约，版本与本地名称改由 `catalog.row()` 详情读取后，专项达到
`69 passed in 10.61s`。随后增加 schema/运行时字段等价、严格日期、非有限与溢出数值、canonical
来源哈希、断连子图 cycle 和基金穿透路径最新日期用例，并加固穿透实现；最终 Stage 3 专项为
`92 passed in 10.90s`，其中七个真实 sandbox 近上限用例均断言 `<10s`、`<1 GiB peak RSS` 且完整
stdout `<=65,536 bytes`。

规范复审后按 TDD 新增收据伪造、provider 不一致、未核验 DataHub、混合快照、权重/总权重杠杆、
显式因子口径、拥挤度日历与总额、穿透聚合前计数、景气度嵌套投影和七项超限反例。实现前 RED 为
`26 failed, 89 passed`；首轮 GREEN 为 `115 passed, 1 failed`，唯一剩余是登记器缺失错误码被通用证据
错误包装。补充 Stage 3 已安装初始版本迁移测试后，RED 为 `7 failed, 1 passed`，实现精确摘要迁移后
聚焦结果为 `8 passed`。

Important 复审按 TDD 新增组合基准偏离混合报告期/行业映射版本，以及行业拥挤度单滚动观测反例：
实现前分别为 `2 failed`（实际 `unknown_field`）和 `1 failed`（未抛错）；逐条等价门禁与
`rolling_days + 1` 历史下限实现后，相关 schema/golden 聚焦为 `16 passed`。Stage 3 全量为
`136 passed in 34.49s`，Stage 2 + Stage 3 清除 `ALL_PROXY`/`all_proxy` 后为
`290 passed in 105.67s`。

最终阻断复审继续按 TDD 收口三处问题：receipt gate 的 selection 与无登记密钥重启场景先观察到
`2 failed`；组合基准偏离的七个 canonical 资产字段冲突用例均先返回 `unknown_field` 而非预期的
`data_not_equivalent`；基金穿透构造 129 边、43 owner、15 层、`3**15` 条逻辑路径的汇合 DAG，旧
逐路径实现于真实 sandbox 9 秒超时。实现启动/选择双重 receipt 审计、跨 book canonical 资产事实
门禁，以及拓扑检环加逐层 DP 聚合后，receipt 聚焦为 `2 passed in 6.19s`，schema/golden/canonical/DAG
聚焦为 `24 passed in 0.79s`，Stage 3 全量为 `144 passed in 30.11s`，Stage 2 + Stage 3 清除代理环境
后首次为 `300 passed in 104.52s`，提交前最终新鲜复跑为 `300 passed in 298.27s`。新 DAG 用例在
sandbox 内约 1 秒完成并保持 `<1 GiB peak RSS`。

直接父版本迁移阻断按 TDD 增加两个参数化回归：先由真实 `record_comparison_receipt()` 生成并复核
合法 v2 receipt，再构造已启用父版本及原生投影。实现前聚焦 RED 为 `2 failed`，均准确失败在重启后
版本未递增；把两个精确父脚本摘要加入白名单并让迁移器兼容单摘要/摘要集合后，聚焦 GREEN（同时
覆盖原始旧摘要兼容）为 `9 passed, 137 deselected in 37.36s`。断言覆盖新版本 disabled、旧投影撤下、
旧 receipt 仅绑定旧版本、新版本无 receipt、active script 切换为当前摘要且不生成新原生投影。修复后
Stage 2 + Stage 3 清除代理环境并禁用外部 pytest 插件自动加载的全量结果为
`302 passed, 1 warning in 167.29s`；warning 仅为当前 pytest 配置中的未知 `asyncio_mode` 选项。
格式化后对同一聚焦集的新鲜复跑为 `9 passed, 137 deselected, 1 warning in 238.29s`。

- 目标 Python 文件通过 `ruff check`、`black --check` 与 `isort --check-only`。
- `catalog.py`、`seeds.py` 与共享输入契约合并通过 `mypy --follow-imports=skip`；七个
  `calculate.py` 也按独立 Skill 包的真实模块边界逐项通过，避免同名模块 `calculate` 冲突。
- Stage 2 + Stage 3 全量首轮为 `285 passed, 2 failed in 101.39s`；两处失败仅因组合重合度和组合基准
  偏离的 `SKILL.md` 缺少文档契约要求的“截止”措辞。同步快照/报告/因子截止口径后，聚焦文档契约
  `7 passed`，最终全量为 `287 passed in 99.51s`。
- capability、admission、native、review、safety、CPU budget 与 sandbox 联合回归首次受宿主
  `ALL_PROXY=socks5://127.0.0.1:29757` 污染：venv 未安装可选 `socksio`，得到 `1 failed, 68 passed,
  3 skipped, 111 errors`；这不是产品依赖缺失，未安装新包。清除 `all_proxy`/`ALL_PROXY` 后原命令
  最终复验为 `180 passed, 3 skipped, 1 warning in 525.58s`；warning 为 Starlette/anyio 第三方弃用提示。
- 七包 49 份 JSON（含七个 source artifact）解析通过。普通索引生成命令因工作树 16 个未改动
  `__init__.py` 是 macOS dataless placeholder 而阻塞；使用只读 `git show :path` 为这些文件供给索引
  生成器后，`docs/generated/py_file_index.md` 成功重建。架构、doc-sync、显式传入全部变更文件的
  project constraints、task completion 与 `git diff --check` 均通过。
- 最终五个变更 Python 文件通过 Ruff、Black、isort；`catalog.py` 与两个 calculator 分别按真实模块
  边界通过 mypy。首轮最终 mypy 暴露基金穿透函数复用局部变量名导致二元 exposure key 被推断为
  三元 edge key 的 5 个类型错误；最小重命名后同一 mypy 通过，基金穿透聚焦回归为
  `6 passed, 138 deselected in 1.13s`。
- Python 索引生成器最终直接成功运行，并把新增 `_audit_enabled_receipt_gates` 方法写入受管索引；该
  生成差异随本次提交交付。补齐 runtime/capabilities 所要求的系统、Tabbit 边界与 review record 后，
  显式最终变更集的 architecture、project constraints、doc sync、task completion 与
  `git diff --check` 全部通过。

不会把未执行的平台或真实数据验证写成已通过。

## 未验证项

本阶段未调用真实 Wind、网络、GPU、Excel 或 VBA，未生成可用于启用的真实 comparison receipt，也未
验证外部 Provider 的字段可用性或数据质量。两份工作簿仅核验给定的完整 SHA-256，未执行其公式或
宏；另五组原始来源不可用。Web-only 变更未修改桌面专属路径，不能由本地离线测试推导 Windows、
桌面或 Excel 运行结论。因此七项能力仍保持 disabled，后续必须取得真实、可重算的 macOS
Wind/Excel comparison evidence artifact 并由宿主可信登记器签名后才能进入启用验收。HMAC 边界用于
阻止普通 JSON 和 sandbox 内计算器自证，不声称抵御已取得宿主环境密钥或本机管理员权限的攻击者。
