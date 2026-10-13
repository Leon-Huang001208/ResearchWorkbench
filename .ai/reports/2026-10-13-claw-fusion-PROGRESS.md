# Claw 首版融合实施进度

宿主 macOS，功能开发，分支 codex/claw-fusion-20261013。用户已批准首版设计及独立测试环境依赖安装；主工作区和正式实例未修改。

## 已实施

本地项目元数据与会话归属、来源文件聚合和显式受控复制；Claw 四入口复用现有能力/MCP/Automation；原生模型工具只能提出锁版本日程草稿，确认后保存为停用任务。

## 验证与环境

项目现有 Web 环境没有 pytest；经用户同意，测试工具安装到 /tmp/rwb-claw-tests-20261013。运行 Web 测试使用项目现有解释器并通过 PYTHONPATH 引入该测试环境，确保文档沙箱使用已有运行依赖。pytest 的 confcutdir 使用项目 Router 已规定的 tests/research_web，不绕过仓库验收。

最终核心 Python：112 passed、2 skipped，198.61 秒；包含项目、日程草稿、API、Store、Automation 与能力原生契约。最终 JS：211 passed、1 skipped，8.073 秒；另有 Router 通用 JS 28/28。跳过的原生测试保留缺失运行依赖状态，不算原生成功。
Ruff、Black、isort、mypy（7 个变更源码）、架构清单、完整 changed set 的 Project Constraints、文档治理、API Atlas 和 Python 文件索引检查通过。完整输出保存在 logs/claw-fusion/；日志哈希和计数可从该目录回查。

实际 Python 命令使用项目现有 .venv/bin/python（PYTHONPATH 指向已批准的临时测试工具环境）：`-m pytest tests/research_web/test_api.py tests/research_web/test_store.py tests/research_web/test_claw_projects.py tests/research_web/test_automation_drafts.py tests/research_web/test_automation_routes.py tests/research_web/test_automation_service.py tests/research_web/test_automation_schedule.py tests/research_web/test_capabilities_native.py --confcutdir=tests/research_web -q`。JS 核心命令包含新增两项、UI、布局、guard、method、能力UI、public-data、architecture 的九个 test 文件。

## 评审修复

Python 评审发现旧确认请求可复活已删除日程、打开目标根失败未清理来源句柄；已写失败回归并修复，原测试组合 9/9 通过。
JS 评审发现文件引用/创建请求陈旧结果会抢回导航、接收会话在重绘后丢失；已增加 generation 校验，附件写回原接收会话草稿，接收选择持久于页面状态并在项目切换时清空。
日程在运行会话 SSE 重绘时丢焦点、项目改名编辑丢失会阻碍用户完成操作，已升级为重要问题并修复，6 项 UI 回归通过。新增迟到附件控制器回归证明附件仍属于原接收会话，并保留原问题。无再次委派评审；最终以复现回归与全闭包验证修复。
Final: minor (deferred): 新增 CSS 的 --border token 尚未映射现有 --line，边框可能不可见；不改变操作和权限，但候选视觉验收前应修正。保留为已知次要缺口。

## 验收状态

本地功能回归通过，但本平台总验收为 BLOCKED。完整 Router Python 闭包为 584 passed、8 failed、1 skipped，79.25 秒；8 项均为 `test_service_manager.py::test_fix4_fresh_failure_restores_only_with_exact_recovery_proof` 参数化用例。已在未修改的主 checkout 重跑得到同样 8 failed（3.25 秒），且 service_manager.py 与基线字节一致，证实为原有基线问题；未在本 Claw 分支修改该启动生命周期逻辑或削弱断言。

真实内置浏览器候选：BLOCKED，开发宿主回环 API 可由 curl 访问，浏览器返回 ERR_CONNECTION_REFUSED，并拒绝错误页的 data: URL；未绕过 URL 策略。临时 UI 候选仅使用 NativeFixture、私有临时数据根和内存 keyring，不是模型研究证据。
真实模型/文件旅程：NOT_RUN。同平台 macOS 干净安装 CI：NOT_RUN。Windows/Linux：NOT_RUN，交接对应设备；本任务不 dispatch 他平台。远端发布与正式部署：未授权、未执行。

安装合同核对：requirements/web.in、requirements/web.lock、scripts/setup_web.py、bootstrap workflow 不需产品依赖变更；test_setup_web.py 已包含在本地 Router 闭包，但干净 macOS 安装 CI 仍未执行。Router 对新增测试和生成页面保留 unknown_impact_boundary 的 L4 升级，不降低风险门。

下一步：独立处理主线启动回归的基线失败，恢复内置浏览器到开发宿主的候选访问，再完成真实 DSH/模型旅程和授权后的同平台 CI；当前不能宣布完整验收或发布就绪。

## 架构决定

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"新增四入口与项目索引投影沿既有原生UI模块组织，不改变Host/DSH边界与研究执行图。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"项目与草稿接口由既有FastAPI Host管理索引，研究会话与正文仍只由DSH执行和持有。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"复用原实例私有认证提出草稿，不增加DataHub查询或来源准入，项目仅展示已有资料摘要。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"草稿确认调用既有Automation创建服务并默认停用，未增加调度器或另一研究执行循环。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"提出工具沿原生research-tools注册、最终guard和私有控制通道，不增加宿主访问能力或生命周期。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"真实能力目录与版本选择保持原权威来源，只登记内部日程提出工具，不新增能力编排或授权来源。","diagrams":[]} -->
