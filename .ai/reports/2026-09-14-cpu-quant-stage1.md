# CPU 有界投研 Skill 阶段 1 实施报告

## 范围

本阶段只建立 Research Web 公共底座：宿主脚本 FIFO、Python readiness、数值线程环境、CPU 工作量
预算、受限 Wind DataHub provider/binding，以及后续 reviewed calculator 可复制的结果和 provenance
资源。未新增 18 个业务 Skill、依赖或公开顶层 API；为保证只读自动查询不触碰用户工作簿，Wind
client/adapter 仅增加独立应用生命周期和显式关闭能力，并同步桌面边界文档与生成索引。

## 安全边界

- 脚本全局单执行，排队超时 `runtime_busy`；取消排队项不创建进程。
- readiness 只检查配置解释器，不回退；源码、输入、输出和凭据不进入队列日志。
- Wind 不接受公式、表达式、路径或凭据；capability/dataset 使用固定输出 schema 并拒绝未知返回列；
  不等价能力固定 `data_not_equivalent`，无真实方法的宏观/利率、基金持仓和大宗交易不登记为 Wind
  callable。只有 xlwings/Excel 适配路径就绪且市场为 `.SH`/`.SZ`/`.BJ` A 股时才可路由；响应逐行
  核对证券身份和日期，指数点位及融券余量分别为 points、share。Wind 历史行情与实时快照只接受显式股票类型，
  日线/资金流/融资融券在任何 adapter 调用前验证日期顺序与含首尾日期的 60 日历日硬跨度。每次
  自动调用创建隐藏独立 Excel 应用/workbook，finally 不保存关闭；单 worker 的 18 秒 deadline 在
  超时/取消后仍等待底层调用关闭，期间稳定 `provider_busy`。关键字段全空失败，部分请求字段缺失或
  请求终点未覆盖时返回 partial。
- 预算超限 `workload_too_large`，不偷偷截断；专业来源 rights 为 `internal-only`。
- 无 GPU 依赖；Seatbelt 仍只支持 macOS，Windows 不执行 provider。
- 脚本被强杀但 child 尚未 close 时保持 FIFO 槽和 poisoned busy 状态；实际 close 或 runtime 重启后恢复。
- child `error` 不作为 close 证据；Wind workbook/app quit 未确认时返回 `wind_cleanup_failed`、保留
  client 所有权，并将 Provider poison 至进程重启，后续查询不创建新 Excel。

## 验证

严格 TDD 的 RED 证据：新增阶段用例首次运行得到 21 failed / 4 passed；FIFO 单例用例在实现前观察到
并发启动顺序失败。规格审查修复再次先补测试，得到 8 个预期失败，分别命中 Wind callable 误报、
adapter 未知列直出、非标量 adjustment 错误分类、非对象 readiness payload 和非规范指数日期投影；
第二轮复审新增测试首先得到 14 个预期失败，命中龙虎榜误作大宗交易、WindPy/client_api readiness
误报、市场范围过宽、两项单位错误，以及响应证券身份和日期未核对。第三轮先得到 Python 10 个预期
失败和 Node bridge 1 个预期失败，命中 asset_type 契约缺口、指数/ETF 误走股票行情，以及反向、
超长或非字符串日期在 adapter 可用性检查之后才拒绝。补充复审再得到 Python 5 个预期失败与 Node
bridge 1 个预期失败，覆盖 snapshot 契约缺口、非股票/缺失类型仍触碰 adapter 和 catalog 资产误报；
随后完成最小实现。代码质量复审继续先补 16 个预期失败，覆盖用户 workbook 隔离/专用 app 关闭、
Wind adapter 回收、1,000 行截断、请求终点、单 worker deadline/取消、七类 schema 最低字段、请求字段
partial 与强杀未 close 的 FIFO poison 竞态；完成实现后定向回归为 193 passed、1 skipped。
末轮质量复审再先取得 3 个 RED：kill 后 `error` 无 close、Excel quit side effect 被静默吞掉，以及
cleanup 失败后新建 adapter；修复后对应 3 项均通过，定向 Wind/DataHub/sandbox 回归为 196 passed、
1 skipped。最终门禁结果如下：

- `python -m pytest --confcutdir=tests/research_web tests/research_web/test_cpu_budget.py
  tests/research_web/test_datahub_catalog.py tests/research_web/test_datahub_wind.py
  tests/research_web/test_runtime_launch.py tests/research_web/test_sandbox.py
  tests/unit/test_wind_adapter.py -q`：243 passed，1 skipped；涵盖四并发 FIFO、排队取消/超时、
  child close/poison 竞态、线程环境、readiness、预算边界、Wind 生命周期与 DataHub 回归。
- `node --test tests/javascript/research_web_public_data.test.mjs tests/javascript/research_web_guard.test.mjs
  tests/javascript/research_web_capabilities_ui.test.mjs`：50 passed，1 skipped。
- 新增/改动的 Provider、client 与测试文件执行完整 `ruff check` 通过；历史 `wind_adapter.py` 对本次
  改动执行 E/F/I 规则通过（其全规则仍有既有 BLE001/B023/RUF012/DTZ001 基线，不在本轮扩改）。
  八个目标 Python 文件 `black --check`、`isort --check-only` 均通过。
- 目标 Python 文件 `mypy --follow-imports=skip`：通过；包含 `sandbox.py` 的常规 mypy 仍报告四个
  既有 dataclass-transform 构造器错误，未改动对应构造调用。
- `node --check app/research_web/runtime/public-data.mjs`、
  `node --check app/research_web/runtime/research-tools.mjs`、`scripts/check_research_architecture.mjs`、
  `scripts/check_doc_sync.py`、`scripts/check_task_completion.py`、生成的 `py_file_index` 重建与
  `git diff --check`：通过。
- Harness 任务 `task-20260914-0f1ff363f777` 已建账；本隔离子分支未获远端交付范围，最终
  `harness-enforce --require-delivery` 因没有 completed/passed delivery outcome 返回失败，留给父任务
  集成与发布阶段闭环。

所有 Wind 用例使用 fake adapter，不访问真实 Wind 或网络。未执行真实 Wind 登录/字段口径、Windows
原生沙箱或 GPU 验证；本阶段也不宣称这些平台能力。
