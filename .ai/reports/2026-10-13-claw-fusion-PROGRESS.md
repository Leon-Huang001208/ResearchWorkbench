# Claw 首版融合实施进度

宿主 Mac mini/macOS，功能开发，分支 codex/claw-fusion-20261013。用户已批准首版设计、任务测试依赖、独立 Native 安装和候选本机 Keychain 复用。主工作区源码及既有 Docker 实例未修改。

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
继续收口已将 Claw CSS 修正为现有 --line，浅色/深色真实边框均为 1px，390px 移动布局无水平溢出。启动恢复的 8 个参数用例固定端口选择，确定进入地址变更事务；另新增同地址不改写断言，不修改生产生命周期代码。
真实 DSH 研究暴露 subagent.list 字段适配缺陷：固定 DSH session/list 输出 parentSessionId，客户端此前检查 parentSession。修正字段并保留 parent、origin、running 类型的拒绝检查，新增四项失败关闭回归。独立 Python 评审未发现重要问题。
真实浏览器发现会话返回项目入口丢组，已修复导航并通过真实点击验收。刷新发现编辑器内存草稿丢失，已增加本标签页 sessionStorage 中按会话隔离的文字和显式附件副本；不恢复工具授权、能力选择或实时标签页。评审发现写读附件数量限制不一致，已统一验证并补充超限保留旧有效副本的回归。

## 验收状态

继续收口完整 Router 与功能 Python 闭包：751 passed、3 skipped、1 warning，277.64 秒，logs/claw-fusion/closure-full-python.log。跳过项仍按原原因保留，不当作原生成功。Ruff、Black、isort 检查 14 个变更 Python 文件通过，mypy 检查 8 个变更源码通过。完整 changed set 的 Project Constraints、架构、文档治理、Python 索引全部通过。
最终 JavaScript 合并闭包 228 passed、1 skipped，7.958 秒，closure-final-js.log；覆盖 Router 通用门、UI、项目/日程、guard、方法、public-data、主题和移动布局。回归新增项均已实际运行；跳过项不认证为通过。

真实内置浏览器已稳定访问独立 Native 候选 127.0.0.1:18189，DSH 13189；无需新增转发、公网暴露或绕过浏览器策略。现有 Docker stage 18088 仅只读确认，不用于本次真实模型旅程。
候选根为 /Users/leon/.research-workbench/acceptance/claw-20261013，公开 SetupWebInstaller 安装入口完成 web.lock、CJPY、固定 DSH 48504f07 构建。任务局部官方 Node v24.19.0 包与 SHA 已核验；现有系统 Keychain 秘密只在本机进程内复用到候选命名空间，不进入聊天、日志或 Docker。
安装期间一次 CLI 误调用忽略自定义 HOME，曾把默认 Native 清单置为 installing；用户独立批准后，已从主线 b610f122 使用正式 install(repair=True,start=False) 完成真实修复。默认清单恢复 installed；没有启动/停止默认服务或变更模型 key，证据 closure-default-native-repair.log。
真实模型测试 passed（deepseek-official/deepseek-flash）；实际研究会话 48c53a84-7177-4504-9ba0-f805a641e61b 与唯一原生子 Agent 54194209-c204-463b-8d1a-9900b3682add 均 completed，父回复非空，交付 completed。真实生成 outputs/claw-acceptance.md，2088 字节，SHA256 76fac170fa71b06073b5eb87a2826c607d656f5140a0856622c2b692c3589954。输入是明确声明的合成数学样本；执行引擎、模型调用、子 Agent、文件交付均真实，未用合成运行时夹具替代。沙箱拒绝及 12 项失败活动保留，未隐藏。
真实项目创建、改名、移组往返、归档/恢复、文件聚合、显式复制、下载哈希和刷新归属/草稿已验收。接收会话 f684c09d-b159-4c08-bff2-1c32739156f4 没有发送消息；复制的两个附件均匹配真实产物哈希。
真实模型调用 rwb_prepare_automation 提出两份草稿；UI 取消第一份、编辑第二份后确认，保存 enabled=false/next_run_at=null。重复确认返回同一 ID；取消后确认和删除后重放均 409，未复活任务。目标 document-reading v1 已注册但有 data_contract_missing 准入缺口，本次仅提出并保存停用计划，未执行或启用该目标；真实研究在未选择能力模板的原生会话完成，没有放宽能力准入。
同平台 macOS 干净安装 CI：NOT_RUN，等待独立远端授权及 exact candidate SHA 证据。Windows/Linux：NOT_RUN，交接对应设备；本任务不 dispatch 他平台。远端发布、合并及正式部署未执行；本平台尚不能记为完整完成。

安装合同核对：requirements/web.in、requirements/web.lock、scripts/setup_web.py、bootstrap workflow 不需产品依赖变更；test_setup_web.py 已包含在本地 Router 闭包，但干净 macOS 安装 CI 仍未执行。Router 对新增测试和生成页面保留 unknown_impact_boundary 的 L4 升级，不降低风险门。

下一步：完成最终候选提交绑定的安装/Doctor、机械回执与授权后的 macOS CI；当前不能宣布远端交付或跨平台发布就绪。证据及截图集中在 logs/claw-fusion/closure-* 与 screenshots/。

## 架构决定

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"新增四入口与项目索引投影沿既有原生UI模块组织，不改变Host/DSH边界与研究执行图。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"项目与草稿接口由既有FastAPI Host管理索引，研究会话与正文仍只由DSH执行和持有。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"复用原实例私有认证提出草稿，不增加DataHub查询或来源准入，项目仅展示已有资料摘要。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"草稿确认调用既有Automation创建服务并默认停用，未增加调度器或另一研究执行循环。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"提出工具沿原生research-tools注册、最终guard和私有控制通道，不增加宿主访问能力或生命周期。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"真实能力目录与版本选择保持原权威来源，只登记内部日程提出工具，不新增能力编排或授权来源。","diagrams":[]} -->
