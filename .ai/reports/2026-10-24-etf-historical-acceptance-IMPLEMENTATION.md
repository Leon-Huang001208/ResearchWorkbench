# 华安 ETF 周报独立历史验收实现

将同一强制不可用Keyring条件扩大到Mac原生沙盒合成验收后，发现原3组正式API/正式Excel/历史Excel夹具也未隔离默认凭据（451 passed/3 failed，85.98秒）；这些Mac-only用例在Ubuntu原CI中跳过，因此未显示在原唯一失败中。对该模块同样显式复用原内存夹具，保留真实DataHub/DSH协议/沙盒/Host质量链与全部断言；不通过放宽产品凭据策略解决。原红灯保留，后续同条件绿灯另行记录。

首轮组合CI（40046249178）实际5369 passed、71 skipped、115 subtests，唯一失败为新增API测试隐式读取系统Keyring。导入NativeFixture类不会自动注册原模块的autouse凭据夹具；Mac本机可用Keychain掩盖了这个测试隔离缺口，Ubuntu正确以credential_store_unavailable拒绝。以任务进程PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring真实复现1 failed（2.50秒），随后显式复用原isolated_keyring内存夹具，保持全部路由断言及真实产品凭据拒绝策略不变。修复只改测试与本报告，不改产品、依赖、CI清单或固定P2；原失败日志保存在私有验收证据目录，修复候选及新CI另行绑定。 修复后同一不可用Keyring进程条件下历史32项与原集成24项共56 passed（41.02秒），没有接触宿主Keychain；完整green日志与XML在logs/etf-historical/keyring-green.*。

主任务产品冻结记录：14文件广回归在可见性封闭修复后504 passed，164.87秒；最后仅增加类型注解，原函数逆替换字节相同，历史/renderer另49项复验通过。9组JS合同241 passed；独立规格/代码质量均批准最终17文件清单e2cbbe73afb1750291c65c7304c3b9ef26392689267f1fb0628e0deb13e8cad4，独立mypy9应用文件通过。完整改动集项目约束、文档/架构初检通过，最终组合候选/CI另行绑定。第一次广回归的11个spawn失败确因主任务stdin入口，实际main runner重跑原workflows60 passed，原始失败保留。

09/10图已真实生成并通过showcase9项/0几何错误/0警告及四视口包含检查；已查看两图最小/最大视口明暗共8截图。09时序默认全景标注偏小，视觉复核明确记录需放大阅读，不宣称每条初屏文字舒适可读。API inventory现399条声明/396唯一操作，阅读页由正式构建器生成；实际产物回执原样同步，没有改写哈希来认证旧图。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"原周报详情内增加显式历史按钮与用途状态，没有新页面组件或导航拓扑；原UI节点抽象保持，具体报告分支已由09和10图更新","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"冻结Run用途在已有私有周报采集调用中传播，来源和Host数据快照拓扑不增节点或新源；原数据图抽象准确，历史分支在09和10报告图标明","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只向既有Checks同一pytest步骤追加历史验收测试，原job和runner依赖超时及平台归属不变，没有新的执行或部署拓扑","diagrams":[]} -->

宿主 macOS / Mac mini；任务类型为 Web 功能开发，隔离任务 etf-historical-acceptance-20261024。
实现未安装依赖、调用 Wind/Office/模型、变更生产服务、读取秘密、提交或发布。独立真实生产验收仍 NOT_RUN。

## 改动与信任边界

专用 historical-acceptance-runs 路由固定 execution_purpose=historical_acceptance，普通 runs 固定默认 formal。
既有 Runtime 验证华安 Excel 已发布合同和主管理员，保存用途；报告期、版本、用途共同去重。
用途与早期会话 marker、持久 Run、冻结 weekly_production 和上下文摘要绑定；恢复和重试复用既有研究，未知受理不重发。
私有 DataHub 从持久 Run 归属派生用途，传到原 Excel Provider、独立数据评估、工作簿投影和质量复算。
快照自身 historical 标记不能选择评估模式；正式模式仍拒绝事后复核。

历史分支只改变同日期采集的正式资格判断，仍检查真实开始/冻结及检索时间范围、全部市场与日历、同版本原件独立重放、历史补点、数字、引用、正文和最终文件。
原历史失败先于其次级经济重放错误呈现；其他经济错误仍保持原门。
Word/HTML 在既有受审沙箱渲染中接收 Host 独立参数，于最终哈希前插入可见历史标识、期间和真实采集/冻结说明。
绑定、下载再检及公共状态均复核当前字节，正文仍唯一 research-report.json。

历史完成保留质量 passed、文件 complete，但终态 historical_acceptance / not_eligible_historical。
仍执行共用交付绑定全部检查，formal finalization_binding 明确拒绝；_finish_run 另挡伪正式提交。
不更新 last_finalized 指针，不满足 manual_weekly_passed 或启用日程，上一正式稿继续保留。
UI 增加明显专用入口与中文用途/资格，当前正式验收卡排除历史运行，历史文件和研究入口仍可查看。

## 实际验证

共同环境：PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages；解释器 /Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python；pytest 加 --confcutdir=tests/research_web -o addopts=。

- 首次红灯：新增历史 Provider/错误优先级两个测试实际失败，logs/etf-historical/red.log。
- 历史数据+经济原件字段：34 passed，economic-focused.log。
- 新历史/runtime+既有质量：37 passed，historical-runtime.log（此时新增历史主模块9例）。
- 扩展原完整质量验收：正式API、正式Excel、历史Excel三组均通过真实 Host 数字/正文/模板/受审沙箱/文件/归档链，3 passed，acceptance-focused.log。
- 最终历史主模块12例：12 passed，historical-final2.log；覆盖显式API、伪purpose、未知受理去重/重试、采集撤权、单点篡改、重启只观察及恢复撤权。
- JS 两个既有模块：15 passed，js-focused.log；历史用途即使伪标 finalized 也不计正式验收。
- 早期组合回归355 passed/6 failed保留regression.log：5为旧测试fixture未接新kwargs，已修fixture；1为经济缺tag优先级，已收窄前置历史判断并由34例复验。未将早期失败擦除。
- 最终完整改动集 Router、CI、独立评审、实际生产/认证下载/Word逐页验收与发布收尾由 root 汇总；此处不冒称已执行。

## 结构复核

仍为原 FastAPI/ReportWorkflowRuntime → 私有 DataHub → 唯一 DSH → 原 Host 质量和沙箱排版，没有新服务、执行引擎、正文库或调度器。
新增 HTTP 受理合同与 Host 用途分支、先标识后哈希和历史终态属于既有节点内部的数据/状态流变化。
因此09/10图应记录正式与历史验收分支，不能以空 diagrams 宣称旧图完全覆盖新合同；图文同步由 root 完成。

<!-- architecture-review {"group":"report-workflows","structure":"changed","reason":"既有工作流新增受信历史用途及独立终态和正式拒绝分支，仍复用唯一DSH和全部Host质量门，09/10图需标明该状态流","diagrams":["09-report-workflow-sequence","10-excel-report-dataflow"]} -->
<!-- architecture-review {"group":"files","structure":"changed","reason":"历史Word及HTML在原沙箱确定性标识后才绑定哈希，并在原下载和交付门再验用途与可见标识，不新增正文库或渲染引擎","diagrams":["09-report-workflow-sequence","10-excel-report-dataflow"]} -->

## 最终实现快照

- 最终定点三模块：72 passed / 1 个既有 Starlette anyio 弃用警告，8.36 秒，final-focused.log。
- 目标12个Python文件 Ruff、Black检查和 isort 检查均通过，git diff --check 通过。
- 17个实现/测试文件 SHA256 清单：logs/etf-historical/implementation-sourcehash.json；清单 SHA256 为 9cc54748db3bb4b63d72d13dd9bca5d873c72eb44de8825dbb4eb48fe4d083ed。
- 所有外部动作未执行；报告期真实Wind、模型质量、Word逐页、生产认证下载及常驻部署仍由主任务单独验收。

## 规格审查修复：可见性与历史资格

独立规格审查发现文本匹配可接受 DOCX 隐藏/删除run或HTML注释banner；同时 public_run 可展示与历史用途矛盾的 finalized。新增反例实际产生5失败（visibility-red.log），未改门绕过。
Word改为核对主body首段唯一run及精确可见黑12pt/bold/vanish=0结构，拒删除、隐藏、移除和改字；HTML从现有lxml解析实际body首aside节点，拒注释、隐藏属性及display:none/visibility:hidden/opacity:0/font-size:0简单CSS。
public_run显式invalidate历史用途的finalized矛盾；历史绑定输出historical_accepted_at及execution_purpose，不再含finalized_at。

- 历史26例+既有质量28例：54 passed，visibility-final.log。
- 原完整正式API/正式Excel/历史Excel三组：3 passed，59.43秒，visibility-acceptance.log；原三图及原正文/文件质量链仍通过。
- 3变更文件Ruff/Black/isort、git diff --check通过。
- 最后清单已刷新：logs/etf-historical/implementation-sourcehash.json；SHA256 c3d990107fb5bc5141978ea6f2db547f0b08a8572ab87819c0dfc5283150b1b3。

## 规格复审修复：封闭 HTML 样式合同

复审补充 transform:scale(0)、color:transparent、font-size:0.0px，以及外联CSS、内联style、缺失style六个反例，修改前全部失败（closed-css-red.log）。
本轮移除CSS隐藏黑名单；受审渲染脚本定义唯一REPORT_HTML_STYLE，Host历史文件门安全导入该常量，要求唯一head style文本逐字相等、html/head/body和meta/title固定、标签/属性为渲染器封闭集合，禁止额外活动标签、link/script和任何内联style/hidden。
原正式HTML样式从HEAD的f-string AST提取并与新常量核对，181字节完全相等。脚本报告分支仅在__main__执行，导入常量无文件生成副作用。

- 历史主模块32 passed：closed-css-green.log；最终相同哈希定点结果见closed-css-final.log。
- 原完整正式API/正式Excel/历史Excel加通用渲染：20 passed，54.94秒，closed-html-acceptance.log。
- 三变更文件Ruff/Black/isort和diff检查通过。
- 最新17文件清单SHA256：892ec5bb3cca2ec825155fcafe202b4871cab31d7aa04e2639e29e27a3cca137。

## 最后类型闭包修正

Host安全导入受审脚本后，既存空列表触发mypy var-annotated；仅给WEEKLY_BLOCK_BINDINGS加list[dict[str,str]]注解，不改任何运行语义。
单模块mypy及Ruff/Black/isort、diff检查通过；历史32+通用renderer17共49 passed（9.37秒），type-annotation-focused.log。
最新实现清单SHA256为e2cbbe73afb1750291c65c7304c3b9ef26392689267f1fb0628e0deb13e8cad4；script SHA256为a701c2174d6a85b548d8539a9999d632c946c29a05f46eeb9a8c3a9040f35f45。
