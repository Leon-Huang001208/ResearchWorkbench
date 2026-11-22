# FinGPT 系统报告流程实施与验收

状态：实施中。宿主 macOS，Web 功能开发；Windows/Linux 原生验收不由本机认证。

用户已批准系统统一处理计算、声明、引用、格式与版本；保留 DSH、数据和模型配置，质量门不放宽。验证后合并部署，最后仅一次原题 Flash 复测。采用 bugfix-evidence、incremental-validation、iteration-delivery。

## 已确认复现与原因

PR149 的单次复测取得两篇正文及四条有全文 SHA/span 的 GDP 观测，但43个脚本活动反复尝试声明、出现派生声明原句与章节不符；原生研究 incomplete。初始无观测时 service 下发旧 payload 路径，取证后没有统一切换。旧生成器还固定生成 PDF 和以段落展示 Markdown 表。

## 实施设计

- 复用原 research_run_script(report_plan)，不增加引擎、循环或模型配置。
- 在原 SDK 新增有界数据配方计算模块，使用精确有理数并最终一次舍入；计算式/操作数由系统写入原生文件且Host重建逐项核对。模型只传真实观测引用、操作和展示位数；不传计算值、单位、引文或源文件路径。Host 评分从实际输入重新提取原始观测并独立重算相同配方，派生观测绑定任务、父来源、原始证据和算法。原 research_quality.py 判据保持。
- plan 统一生成数字声明、同节 notes/coverage、显式缺口；自由 analysis 仍是被检查的文字，不自动认证。跨期间/初步最终配对仅计算，不认证可比性。
- 从冻结 question 的明确格式要求推导 HTML/DOCX；没有明确限制沿用旧默认。Host 独立检查必需格式，模型不能删减。实际 HTML/Word 用已评分的数字声明生成表格；保留原始章节和缺口。
- 取证前后均使用同一份 plan 指导，原生只读 admission 每次提供最新任务和格式上下文；错误提供稳定、可操作的字段原因，不新增补查许可。
- 保留暂存、旧版归档、canonical JSON 最后发布、回滚失败撤下混合版本的原协议；有错误不交付伪绑定。

## 执行计划与验收

- [x] 先写真实 GDP 失败输入驱动的 plan 成功测试，修改前失败为 research_report_plan_fields（before.log）。
- [x] 新配方计算模块及拒绝反例：缺失/歧义、伪值/单位/引文、跨指标、零分母、输入变更。
- [x] plan/Host 独立重算、格式与完整文件投影；旧接口默认兼容。
- [x] 初始无观测→实际read_source回调刷新→系统报告→质量→当前归档和链接完整成功路径。
- [x] 有真实缺口、analysis 未核验和损坏来源不通过；同一次补查修正、重复检查、重启恢复、两/三格式写入及双重回滚失败不产生伪绑定。
- [ ] Router 所有必需本地门、独立评审、对应候选 GitHub 通用与 macOS 安装门。
- [ ] 精确 SHA 空闲事务部署，核验活动/保全/健康；活动或未知研究延后切换。
- [ ] 使用原题 SHA 81385dc8675d5f7c45fae311aa42ca3c1840fbadf84531ea7f9029438e9acd4c，截止2026-10-16，深入模式；900秒/48实际工具/6检索/一次补查，20工具目标另考核，只提交一次同一个 DeepSeek Flash。
- [ ] 独立记录执行、文件和质量状态，归档证据并回收本任务资源；不把离线成功或部署完成冒充真实研究通过。

## 证据

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"扩展原report_plan数据配方和受信context字段，复用同一Host回调与DSH工具，不创建新HTTP端点或状态服务。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"service内报告指导统一不改变Automation准入、调度、凭据与模型选择；仍经原预算及取消通道执行。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"固定SDK内系统组装及Host独立输入重算复用原文件/归档/回执路径，不新增数据库、正文库或迁移。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"原research_run_script保持native admission、runner、slot与预算，仅添加固定纯计算SDK只读文件，无新循环或进程。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"成功和恢复测试加入原Research Web Checks同一步骤，无新job/runner/依赖；原Mac安装门与单次真实研究保持分开。","diagrams":[]} -->

后续仅记录实际执行命令、结果与限制，不预填 PASS。原失败报告不改写，离线样本标明历史记录/受控夹具。

源码检查点：新增calculation/formats/system_flow加原revision合跑122 passed，2.96秒；原生JS工具23 passed；融合路由及受信context四例21.63秒。Ruff/Black/isort和SDK三模块mypy通过。定点命令为现有Python+已安装pytest运行器，带`--confcutdir=tests/research_web`，未安装依赖；详见任务logs。第一次旧模块组合139 passed/1 skipped/1旧指令断言失败，路由改为取证前统一plan后定点闭合；不隐去该次失败。

原失败case完整两篇已取得正文（按原SHA读取）在独立Store离线回放：5条声明、3.99%、原生计算式及HTML/DOCX绑定成功；模型/网络调用均为零。原题完整要求和跨版本可比性缺口保留incomplete，数字/算术/笔记链不再出现原错误。受控成功测试的缩小数字合同不是原题全文验收通过。独立预审发现并修复空引用交付、非规范FOMC观测兼容、96位二次舍入三个问题；有理数边界正负测试和Host底稿篡改拒绝已补。

集成补充：首轮完整API 202通过（1198.987秒），README复核回执缺失被本地约束拒绝，已更新README及回执。另补齐实际交付默认三格式与报告两格式的冻结一致性：service.send→同任务receipt/context→原macOS沙箱文件检查→Host归档的3项回归11.66秒通过，不再以valid=True夹具代替该步骤。新的冻结提交重新评审和验证；其他平台交接不冒充Mac证据。

升级重放补充：独立评审发现默认格式变化会改变旧请求摘要。已有请求只复用同任务回执中冻结的默认展开值，仍逐项比较其他输入；已受理重放不再调用模型，pending/unknown保持受理未知。跨任务或损坏的冻结交付失败关闭。新请求按原题明确格式冻结。完整本地API门可分为三个独立进程，须证明收集/执行集合与原202项完全一致、无遗漏/重复/跳过，才记该门通过。
