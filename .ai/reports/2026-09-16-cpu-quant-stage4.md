# CPU 量化 Skill Stage 4 实施报告

日期：2026-09-16

## 交付范围

本阶段增加五个独立、CPU 有界、仅研究用途的内置 Skill：

- `rate-ma-timing-research`
- `equity-risk-premium-timing`
- `style-rotation-research`
- `platform-breakout`
- `chanlun`

每包包含 `SKILL.md`、独立 `scripts/calculate.py`、严格输入/输出 schema、字段映射、来源
provenance、synthetic source artifact、fixture 与 golden result。五项复用 `cpu_bounded_v1`、安全相对
JSON loader、有限数算术、64 KiB 完整输出、不可变版本与 v2 HMAC comparison receipt，不新增依赖、
顶层 API、Workflow、执行器、Provider binding 或桌面路径。

## 方法与失败边界

- 利率均线：尾随均线与绝对乖离阈值只产生新研究信号；研究敞口使用前一持久信号，避免同日
  前视。历史下限为 `window + 1`。
- 股权风险溢价：固定 `1 / PE_TTM - bond_yield_pct / 100`，经验分位为窗口内小于等于当前值的比例；
  PE 必须为正。
- 风格轮动：调用方必须显式选择相对比值均线或相对强弱动量；未知方法返回 `ambiguous_rule`，
  符号冲突保持 neutral。
- 平台突破：仅处理显式有限观察列表，平台由当前 bar 之前的窗口估计；收盘越过 buffer 且阻力触碰
  次数达标才确认。最多 50 标的、每标的 1,000 行、合计 50,000 行。
- 缠论：只实现严格确认分型与非递归交替笔子集；相等平台、双重枢轴或过近反转返回
  `ambiguous_structure`，不声称覆盖中枢、背驰等完整体系；结果顶层必填回传所有记录共同的
  `asset_id`，全量记录改名会同步改变结果身份，混合标的仍失败关闭。

所有结果包含 `sample_size`、`conditions`、`counterexamples`、`failure_conditions` 与 `data_cutoff`，
并固定 `research_only=true`，不是交易、下单或个性化投资指令。

规格复审后，利率均线、风险溢价与风格轮动的输入和输出均增加必填、provider-aware 的
`series_identity`。每条 descriptor 固定 role/version/tenor 并校验非空 identity 格式：synthetic
精确绑定提交 fixture，`user_input` 可携带真实业务 identity 并原样回传；角色交换、风格重复 identity、
版本或期限错配均返回 `data_not_equivalent`。Wind/DataHub 仅可使用 field mapping 的精确生产白名单，
当前没有已核验身份，保持失败关闭。风格均线乖离方法增加独立 input/golden，平台突破与缠论不可用
来源的 provenance 不再记录本机绝对路径。五包静态检查覆盖完整包，允许 10 份 schema 唯一的官方
Draft 2020-12 元数据 URI，但继续禁止代码和配置的可执行网络能力。

## 来源与状态

三份工作簿只做只读公式/缓存检查，未执行公式或宏，未提交原文件：

- 利率均线：`d01ac5155c1ccd07a7b1d192b555b0a9f0d13e951c3ebe0d4199c85d22d1d028`
- 风险溢价：`1abb2d15f810282ce3617246594de65c02636c57e8b510eff4184dc7044c7ed8`
- 风格轮动：`9450f30aebb1271b05bc04d086f22676d1e793e22822c43b1a5f7bc3e7e6969a`

对指定 Skill 来源树的 152 个文件计算完整 SHA-256 后，平台突破与缠论给定候选前缀均未匹配。
两包 provenance 因而明确 `source_artifacts_available=false` / `source unavailable`，只记录未匹配候选
前缀，不猜测完整摘要。五包 synthetic source artifact 均由 fixture、dataset ref、golden 和 provenance
绑定实际 SHA-256。

能力目录由 25 项更新为 30 项。五项均 `cpu_profile=true`、加入 `RECEIPT_GATED_SKILLS`，clean catalog
中可发现但初始 disabled，不生成原生投影。普通 JSON、自证计算器和伪造签名均不能启用；合法
receipt 只绑定当前不可变版本，发布 successor 后不复用。当前没有可核验的已发布 Stage 4 前身，
所以不建立猜测性迁移 SHA-256 白名单，只验证旧目录新增种子时仍以 disabled 安装。

## TDD 与验证证据

TDD 记录：

- 利率均线首个 golden 用例先 RED：`1 failed`（calculator 不存在），实现后 `1 passed`。
- 其余四项 golden 先 RED：`4 failed, 1 passed`（calculator 不存在），实现后五项主路径 `5 passed`。
- 扩展契约首轮暴露五个测试解析错误：`5 failed, 55 passed`；失败 stderr 按既有 Stage 3 约定包含
  日志行和末行 JSON，测试改为解析末行后通过。
- 注册/回执/压力门完成后 Stage 4 专项：`75 passed, 1 warning in 25.15s`。warning 仅为当前 pytest
  配置中的未知 `asyncio_mode` 选项。
- 格式化后 Stage 2 + Stage 3 + Stage 4 全量：`377 passed, 1 warning in 208.32s`。
- 能力目录、准入、原生投影、审查、安全、CPU 预算和 sandbox 聚焦回归：
  `180 passed, 3 skipped, 1 warning in 564.85s`。首次用禁用插件的命令运行时，除目录数量仍为旧断言
  外，异步用例因 `pytest-asyncio` 未加载而不能执行；数量和新增名称断言同步后，改用正常插件环境
  完整复验通过。
- `scripts/check_doc_sync.py`、`scripts/check_task_completion.py`、52 项 Research Web architecture Node
  测试和 `.agents/project-constraints.mjs` 均通过；新增 37 个 JSON 文件均可解析，`git diff --check`
  及相关 Ruff、Black、isort 检查通过。
- 规格复审修正先增加身份/期限、独立 golden、整包静态扫描和缠论歧义结构测试，初始 RED 为
  `7 failed, 2 passed`；其中缠论双重枢轴与过近反转两项已由现有实现正确失败关闭。最小实现后
  Stage 4 专项 GREEN 为 `83 passed, 1 warning in 25.83s`，Stage 2 + Stage 3 + Stage 4 为
  `385 passed, 1 warning in 217.34s`；能力聚焦回归为
  `180 passed, 3 skipped, 1 warning in 553.48s`。
- provider-aware 身份与 schema 自描述复审先得到 `17 failed, 2 passed`；最小实现后的新增/受影响
  定向集为 `24 passed`。空 identity 错误码补充先 RED 为 `1 failed, 4 passed`，修正后 GREEN 为
  `5 passed`。
- 源码冻结后的最终复验：Stage 4 专项 `94 passed in 24.84s`；Stage 2 + Stage 3 + Stage 4 全量
  `396 passed in 207.60s`；能力目录、准入、原生投影、审查、安全、CPU 预算和 sandbox 聚焦回归
  `180 passed, 3 skipped, 1 warning in 1350.11s`。warning 仍仅为当前 pytest 配置中的未知
  `asyncio_mode` 选项；五项 Stage 4 能力在每轮 seed 后均保持 disabled。
- 质量复审针对 comparison input 内容独立性和缠论结果身份先得到 `2 failed, 4 passed`；catalog 增加
  读取后 SHA-256 不同门禁、缠论顶层回传唯一 `asset_id` 后，定向集 GREEN 为 `6 passed in 18.72s`。
  Stage 2/3/4 合法 receipt fixture 均改用内容真实不同但业务可比的 actual input；复制 synthetic 到
  不同路径后重新签名仍返回 `invalid_comparison_evidence`。Stage 4 专项为 `95 passed in 20.68s`；
  receipt helper 增加业务记录等价、source artifact 摘要可追溯与输入字节不同断言后，聚焦复验
  `4 passed in 18.99s`，最终 Stage 2 + Stage 3 + Stage 4 全量为 `398 passed in 178.57s`。
- 最终能力目录、准入、原生投影、审查、安全、CPU 预算和 sandbox 聚焦回归为
  `180 passed, 3 skipped, 1 warning in 719.68s`。相关 Ruff、Black、isort、122 个 Stage 2/3/4 JSON
  解析、文档同步、任务完成检查、52 项架构测试和项目约束均通过。`chanlun` 独立 mypy 与 catalog
  `--follow-imports=skip` 检查通过；catalog 常规 mypy 仍被未触及的 `core/observability/{tracer,metrics}.py`
  和 `data_layer/adapters/wind/wind_adapter.py` 共 15 个既有错误阻断。

近上限真实 sandbox 复测（父进程与子进程 RSS 合计）：

| Skill | 输入行 | wall | peak RSS | 内联输出行 |
| --- | ---: | ---: | ---: | ---: |
| rate-ma-timing-research | 5,000 | 0.200s | 39.7 MiB | 128 |
| equity-risk-premium-timing | 5,000 | 0.202s | 40.3 MiB | 128 |
| style-rotation-research | 5,000 | 0.194s | 38.1 MiB | 128 |
| platform-breakout | 50,000 | 0.343s | 75.0 MiB | 50 |
| chanlun | 5,000 | 0.207s | 38.2 MiB | 0 |

所有 sandbox 成功结果均 `<10s`、`<1 GiB peak RSS`、stdout/stderr 合计 `<=65,536 bytes`；压力成功
只接受 supervisor `completed` 且业务 JSON 可解析，不把 error 当作压力成功。

## 未验证项

未调用真实 Wind、网络、GPU、Excel 或 VBA，未生成可用于启用的真实 comparison receipt，也未验证
DataHub 联合字段映射与真实数据质量。三份工作簿只读核验不等于真实 Excel/Wind 对照；平台突破与
缠论来源不可用。Web-only 变更不属于桌面交付，不能据此声称 Windows 或真实桌面集成已验证。
