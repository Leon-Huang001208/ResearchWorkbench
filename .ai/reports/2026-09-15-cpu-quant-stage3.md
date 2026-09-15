# CPU 有界投研 Skill 阶段 3 实施报告

## 范围

本阶段在既有 `cpu_bounded_v1` 共享契约上新增七个仓库内置、独立、单一职责 Skill：基金匹配、基金
穿透、组合重合度、组合基准偏离、行业景气度、行业象限监控和行业拥挤度监控。每个包均包含受审的
`SKILL.md`、`scripts/calculate.py`、严格输入/输出 schema、DataHub/Wind 字段映射、来源
provenance、synthetic fixture 与 golden result。能力中心通过既有种子、不可变版本与 comparison
receipt 门控登记七项；未新增 Workflow、页面、顶层 API、执行器、依赖或 Stage 4 内容。

## 计算与证据边界

- 基金匹配只对输入给定的风格、风险和业绩特征计算归一化加权 L1 距离；不抓取基金数据，也不生成
  买卖建议。
- 基金穿透统一接受 percent/decimal 权重，支持多层基金持仓和重复路径聚合；对全部给定基金子图做
  环检测（包括根基金不可达的子图），发现 cycle 即失败关闭。重复边采用最新披露日，路径 `as_of`
  传播该路径全部边的最新披露日。
- 组合重合度归一化两侧权重并逐标的取最小值；组合基准偏离计算行业权重偏离及输入因子的标准化
  暴露偏离，不做优化、交易或收益预测。
- 三个行业 Skill 只接受调用方预聚合的行业指标：景气度计算方向调整的加权百分比变化，象限监控按
  给定水平和动量阈值分类，拥挤度监控计算行业成交额占全市场成交额的滚动比例及历史经验分位；均
  不读取个股明细或自行聚合原始行情。
- 七个脚本的 schema 与运行时逐层字段等价：根对象、parameters、dataset ref、每条记录和输出封套
  均拒绝未知字段；严格校验扩展格式 `YYYY-MM-DD`、前视日期、有限数值和受检算术。
- 输入只允许 cwd 内相对 JSON，并复用逐组件 no-follow/句柄复核的安全 loader；不得通过绝对路径、
  `..`、符号链接或 reparse point 逃逸。
- `cpu_bounded_v1` 预算固定为最多 50,000 行、64 MiB 输入、单序列 5,000 点、最多 50 条序列且每条
  1,000 点。完整 strict JSON envelope 不得超过 65,536 UTF-8 bytes，成功 stdout 不附尾随换行；
  超限稳定返回 `workload_too_large` 和 `reduce_scope=true`。
- 静态与运行边界禁止 GPU/CUDA/MPS/Metal、网络、VBA、CJPY、绝对产品路径及隐式数据获取。

## 能力状态与来源

七项在 clean catalog 中可发现、可检查，但初始及迁移状态全部为 disabled。只有绑定当前 slug、不可变
版本、计算脚本摘要、仓库 golden、实际 comparison result、输入来源摘要、macOS `wind_excel`
环境和通过结果的可验证 evidence artifact，才能由 catalog 派生 receipt 并启用；测试生成的 synthetic
artifact 只验证门控机制，不构成真实 Wind/Excel 对照证据。

本阶段只把能够逐字核验的来源写入 provenance：

- 组合基准偏离工作簿 SHA-256：
  `415d61e46b2c390de928c0f33011792d94f70efb508e59176d7aa77168c6c504`。
- 行业拥挤度工作簿 SHA-256：
  `24010fb2dd76604442d89b7ea4c3c691e3cdc198c87bd191ed1aaf020a0bb831`。
- 基金匹配、基金穿透、组合重合度、行业景气度和行业象限监控的原始 Skill/script 在已检查的来源
  位置不可用；对应 provenance 明确记录 `source unavailable`，不猜测 SHA-256，并保持 disabled。

## TDD 与验证

中断恢复时 Stage 3 专项为 `68 passed, 1 failed`，唯一失败是测试从能力列表摘要读取不存在的
`versions` 字段。列表继续只验证摘要契约，版本与本地名称改由 `catalog.row()` 详情读取后，专项达到
`69 passed in 10.61s`。随后增加 schema/运行时字段等价、严格日期、非有限与溢出数值、canonical
来源哈希、断连子图 cycle 和基金穿透路径最新日期用例，并加固穿透实现；最终 Stage 3 专项为
`92 passed in 10.90s`，其中七个真实 sandbox 近上限用例均断言 `<10s`、`<1 GiB peak RSS` 且完整
stdout `<=65,536 bytes`。

- 目标 Python 文件通过 `ruff check`、`black --check` 与 `isort --check-only`。
- `seeds.py` 与七个 `calculate.py` 分别通过 `mypy --follow-imports=skip`。把七个同名脚本一次性传给
  mypy 会触发重复模块名 `calculate`，因此按独立 Skill 包的真实模块边界逐项执行。
- 首轮相关联合回归为 `405 passed, 2 failed, 2 skipped, 1 warning in 431.27s`；两个失败仅是旧测试仍
  固定 18 个 Skill/22 个 Skill+Workflow。将数量更新为 25/29，并补齐七项名称后，Stage 3 全套与
  两个受影响旧契约的最终聚焦组合为 `94 passed, 1 warning in 30.74s`。两个 skip 是原套件声明的
  外部 DSH 条件；warning 是 Starlette/anyio 第三方弃用提示。本轮未重复七分钟级联合套件。
- 七包 42 份 JSON 解析通过，`docs/generated/py_file_index.md` 已重建。架构、doc-sync、显式传入全部
  变更文件的 project constraints、task completion 与 `git diff --check` 均通过。

不会把未执行的平台或真实数据验证写成已通过。

## 未验证项

本阶段未调用真实 Wind、网络、GPU、Excel 或 VBA，未生成可用于启用的真实 comparison receipt，也未
验证外部 Provider 的字段可用性或数据质量。两份工作簿仅核验给定的完整 SHA-256，未执行其公式或
宏；另五组原始来源不可用。Web-only 变更未修改桌面专属路径，不能由本地离线测试推导 Windows、
桌面或 Excel 运行结论。因此七项能力仍保持 disabled，后续必须取得真实、可重算的 macOS
Wind/Excel comparison evidence artifact 才能进入启用验收。
