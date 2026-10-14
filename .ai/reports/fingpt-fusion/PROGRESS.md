# FinGPT 融合执行进度

宿主 macOS；功能开发；本机隔离安装、沙箱和 UI 验收。Windows/Linux 与 GitHub Mac CI 尚未执行。

实现：研究深度/范围锁定、原生 Todo、会话证据、章节笔记、统一 HTML/DOCX/中文 PDF。

评审反例已修复：重复产物、缺笔记链路、旧笔记、受理中草稿丢失、排除来源绕过。独立文件交付认证必须与哈希匹配。

验证：此前核心回归 91 项通过；本轮完整相关模块回归运行中；JS 54 项通过；Ruff、文档治理通过。PDF 中文提取与嵌入字体已实测。

安装：用户已授权并完成官方 Node 24.19.0 头文件 SHA-256 校验，任务内 CMake 3.31.10 与同版本 Node 构建固定 DSH 成功。候选 38088/33081 启动，Doctor installation_ok/product_ready=true，原生工具契约跳过项补跑通过。用户在候选设置页自行配置凭据，并授权一次真实模型验收；一次提交终态 completed、原生 Todo 两项完成、三格式 delivery.completed，下载重开及哈希通过。六次原生工具调用中保留一次真实签名失败，后续恢复；没有重复模型提交。报告 quality=incomplete（缺数据/独立核实及数字复核提醒），不冒称投资研究质量通过。未发布。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "Existing research sidebar/composer own the new projections and immutable choices; no page shell, navigation, theme or engine topology changes.", "diagrams": []} -->
<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "Session request fields extend the existing create/send/detail operations; file upload scope is checked at the existing route boundary.", "diagrams": []} -->
<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "Shared main.py and capability format declarations change; scheduler and delivery channels still use the existing session/report ownership graph.", "diagrams": []} -->
<!-- architecture-review {"group": "files", "structure": "unchanged", "reason": "Three artifact formats use existing session outputs and sandbox delivery parser; evidence projection is a sibling of native event projection.", "diagrams": []} -->
<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "Native Todo plugin registers on the existing DSH tools/sessionProjections providers; Web renders native events and retains the sole DSH engine.", "diagrams": []} -->
<!-- architecture-review {"group": "capabilities", "structure": "unchanged", "reason": "PDF extends existing format declarations and source scope narrows existing preflight; version ownership and MCP approval topology remain intact.", "diagrams": []} -->
<!-- architecture-review {"group": "report-workflows", "structure": "unchanged", "reason": "PDF rendering reuses the existing report renderer and sandbox delivery sequence; no new workflow runner or execution state machine.", "diagrams": []} -->

浏览器：当前内置标签通过新版组件读取/截图成功；CUA 通道仍超时。初版截图暴露快捷按钮竖排及资料范围拥挤，独立类样式修复后强制文档导航核对 flex-direction=row。已验证默认/弹层/深度/快捷草稿；忙碌/旧笔记由回归测试与复审覆盖。

类型：新增证据/报告模块 mypy 通过。全 Web 目录遇既有 workflow 同名冲突；显式文件检查带出基线依赖债务，其中本次 Field 类型错误已修复。ServiceManager/LocalIntegrations 441通过、8失败、1跳过；8失败在未改动主 checkout 同环境复现。总体门不报 PASS。

最终本地证据：API 55通过；协议/恢复/原生计划33通过；中文报告8通过（含真实 Seatbelt）；原生工具 schema 补跑1通过；DSH Todo实际组件配脚本模型11通过；JS核心54及治理146通过。完整相关 Python早期161通过/1跳过，跳过已补跑。模块扩展检查441通过/8基线失败/1跳过，8失败已在未修改基线重现。

候选服务重启首次因显式端口临时占用而失败；核对PID已退出、无监听、绑定探针变为free后使用同一manager恢复，不杀未知进程、不改变端口门。原生历史恢复保留成功及失败状态。

尚未完成：GitHub macos-14干净安装/CI、远端发布、Mac Docker及Windows/Linux真机/CI。它们保持NOT_RUN；本轮本地实现与真实闭环可审阅，不等于完整发布就绪。

Harness 汇总失败：harness-evaluate --task-id fingpt-fusion 返回 invalid task record，未生成通过回执；保留 FAIL，尚未进入受管完整交付。

Harness 后续诊断确认任务记录缺少旧汇总器必需的 outcomes 数组。使用受管 record-outcome 补录实际33项协议/恢复测试（12秒）后汇总恢复；只认证本地目标。observations.sampleSize=0，未冒称已有 runObserved 完整交付/CI 机械回执。
