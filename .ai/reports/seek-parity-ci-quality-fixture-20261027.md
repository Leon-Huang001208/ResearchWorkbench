# 首批场景 CI：真实交付夹具平台归属修复

- 宿主 macOS；任务类型：Web 测试修复；基线 `5b924870`。
- 范围：仅 `tests/research_web/test_scenario_review_round2.py` 与本报告。没有产品代码、依赖、运行时、供应商、模型、常驻或部署变更。
- CI 原证据：`logs/ci-checks-40384650069-full.log:87323-87400`，Ubuntu Checks job `121789592176` 唯一失败，原结果 7212 passed / 72 skipped / 133 subtests。

## 根因与修复

原测试生成真实 HTML，并要求 Host 为来源报告认证 `passed`。`Delivery.refresh` 必须调用原严格 `sandbox.run_script` 解析；`sandbox.py:265` 明确拒绝非 macOS，因此 Ubuntu 正确返回 `verification_failed`，质量保留 `incomplete/report_artifact_delivery_unverified`。这不是 suite 顺序污染；Mac 单独原例通过，强制原 sandbox 的非 darwin 分支后定点复现同一失败。

原 mixed passed/incomplete 测试按既有 `test_delivery.py` 惯例声明 macOS 原生归属。全部原来源顺序、摘要 `not_assessed`、来源逐项质量/contract/report hash 断言保留；新增真实 delivery `completed`、task_id、required_formats、missing_formats 与实际 HTML 字节 SHA 绑定断言。

新增跨平台反例用真实文件、API、Host 投影和导入流程，只让严格沙箱抛出明确不可用错误，不伪造质量或通过回执。canonical JSON 自报 `quality=passed` 仍保持来源 `incomplete`；摘要仍 `not_assessed`，自报 `quality=passed` 的导入摘要被 422 拒绝。共享内部夹具只避免两条路径漂移。

不能以空格式请求代替原真实交付：`_report_formats` 要求 1–3 种格式；`required_report_formats` 在 required_formats=[] 时回退至问题声明或默认 HTML/DOCX/PDF；Host 仍要求每个 artifact 的实际交付绑定。没有放宽该门。

## 实际验证

使用已存在的 release Python `/Users/leon/.local/share/research-workbench/releases/d744029a5/.venv/bin/python`、既有 uv 缓存 pytest 及格式工具；未安装依赖。pytest 必须带 `--confcutdir=tests/research_web`。所有 basetemp 位于本任务专属 `logs/quality-fixture-7c14e8/`，每次使用不同不透明叶目录。

1. Mac 原例基线：`python -m pytest --confcutdir=tests/research_web -q tests/research_web/test_scenario_review_round2.py::test_arbitrary_summary_does_not_inherit_mixed_real_source_report_quality --basetemp=logs/quality-fixture-7c14e8/baseline-1afc91`：1 passed，3.14s；`logs/quality-fixture-baseline-native.log`。
2. RED：仅将 `sandbox` 模块的 sys 引用替换为保留原属性但 platform=linux 的代理，执行原 node id，同一原 guard 拒绝运行：1 failed，2.14s；真实 `incomplete/report_artifact_delivery_unverified`，`logs/quality-fixture-red-nondarwin.log`。未改变 pytest 或全局 sys 平台。
3. GREEN：`python -m pytest --confcutdir=tests/research_web -q tests/research_web/test_scenario_review_round2.py tests/research_web/test_asset_research_workspace.py tests/research_web/test_research_quality.py tests/research_web/test_delivery.py --basetemp=logs/quality-fixture-7c14e8/green-cb08b4`：72 passed，77.44s；`logs/quality-fixture-green-native.log`。
4. 相同模块局部非 darwin 代理执行新增 portable node id：1 passed，2.08s；`logs/quality-fixture-green-nondarwin.log`。
5. 目标文件 ruff、black --check、isort --check-only、git diff --check 通过；分别见 `logs/quality-fixture-{ruff,black,isort}.log`。

初始化的两次非验收调用分别因缺少正式 Web confcutdir、basetemp 父目录尚未创建而未进入用例；日志 `quality-fixture-baseline.log`、`quality-fixture-baseline-web.log` 保留。随后纠正命令和目录，未引入 SQLAlchemy 或其他依赖。

## 交接与限制

未运行 full suite、远端 CI、Linux 原生产品验证或部署。非 darwin 代理只证明原门分支与 portable 反例；不能声明 Linux 原生测试通过。新增 macOS 专属 skip 不代表 Linux 获得 passed 来源认证。最终候选完整闭包、独立评审和远端交付由 controller 统一执行。

必要日志与本任务临时树清理清单写入 `logs/quality-fixture-closeout.json`；仅回收 `logs/quality-fixture-7c14e8/` 的本次临时树，未触碰全局 pytest 或其他任务缓存。
