# Dual-runtime scoped Python quality

hostPlatform=macos；taskKind=既有 Web 功能的 Python 质量整理。
hostAcceptance=BLOCKED；aggregateAcceptance=BLOCKED。本任务无 Docker/服务、远端、安装、
controller 或其他 worktree 写入。基线 ee3c96e552ef12c054d8dc93166b535e3183a5e0；仅允许
c24a8a161..ee3c96e5 的 26 个 changed Python 文件，完整名单见 logs/python-quality/scope.json。
未修改全局机器配置、FollowImports、依赖值、策略、受管 kernel 或旧回执。
主任务另明确批准 pyproject.toml 的唯一 line-length=100 字段，与该文件已有 Black/isort
行宽一致；不改变 Ruff 的 select/ignore/版本，最终仍运行原 ruff check 命令。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Formatting, import order and explicit equivalent spellings keep the existing lifecycle and filesystem proofs; internal typing describes existing validated values and unchanged optional keyword forwarding.","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"No public API, process topology, authentication exchange, control record schema, allocation authority or recovery semantics change.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Updates existing owner documents and records scoped current evidence without changing documentation policy or asserting old source snapshots describe this worktree.","diagrams":[]} -->

## Diagnosis and baseline

主任务原始 ee3 证据为 prepared integration 的 logs/task14-final-{ruff,black,isort}-ee3.log
及 task14-final-python-quality-ee3.json，分别 132 Ruff 诊断、23 Black 文件、11 isort 文件。
这些引用不是本子任务重新执行。当前已有工具版本 Ruff 0.16.10、Black 26.10.0、isort 9.0.2、
mypy 2.4.0；同 macOS 宿主，未安装依赖。

c24 同范围源码经真实 git archive 导出到本 worktree 的 mktemp 诊断目录，4 个新增文件
没有伪基线。实际同工具/config 检查为 Ruff 54、Black 11、isort 6；详细原命令、退出码和
耗时保存在 logs/python-quality/records.json。11 个 kernel 文件 SHA-256 校验均一致。

mypy 独立工具最初缺项目配置要求的 pydantic 插件依赖；只读复用原已批准产品 venv 的
site-packages 后，历史额外 --follow-imports=skip 命令对 c24 为 107 诊断/14 生产文件，
ee3 为 120/16，107 条签名均保留。10 条真实新增局部类型说明已处理；剩余 3 条属于相同
stub-skip 模式在新 dataclass/类型别名使用位置的表现，不添加 type-ignore。
另一次不带额外 skip 的项目正常配置诊断为 72 条/23 文件（16 个入口加导入闭包），
上述 3 条消失。随后按实际解析图归档 c24 的 208 个本仓传递源码（只作诊断，不部署），
同版本正常配置基线为 59 条；局部类型整理后当前也是 59 条，file+message 多重集一致，
无新增或移除。正常配置与额外 skip 命令分开记录；完整 mypy 仍 FAIL，不能称作 PASS。

## Scope and semantic checks

首轮 isort/Black 后，26 文件的非导入 AST 和导入集合全部相同；10 文件仅导入顺序 AST
变化。随后逐点处理显式 check=False、未使用测试绑定、等价字面量/正则拼写、上下文与条件
合并；上下文进入/退出顺序和布尔短路顺序保留。同步回调仅显式捕获当前循环变量。
安全拒绝、日志 handler 失败和清理中断的宽捕获保留具体单行理由，不记录异常秘密正文。
类型说明不新增输入修复或运行时授权，也不处理首次 Docker 启动后的另一路生命周期问题。

Ruff 默认 88 列与既有 Black/isort 100 列曾产生 14 条 I001 导入格式冲突；原失败日志保留。
经主任务明确批准仅对齐项目行宽后，26 文件 Ruff/Black/isort 已通过，无规则削减或临时 CLI
行宽覆盖。生成索引仅新增两个内部 TypedDict 和相应 typing import，首次 stale 失败记录保留。
源码检查与最终测试结果见下方；不宣称整体 mypy 或本质量分支实机验收通过。

## Preserved failures

首轮 runtime-mode 闭包 315 PASS / 7 FAIL：原 setup_web.port_busy 导入虽在模块内未调用，
仍是既有 repair 测试使用的模块绑定。已恢复显式同名 re-export，并为这一兼容绑定标注
精确 PLC0414 例外，保留原绑定和断言。尝试普通 unused import 注释时的格式冲突已收敛，
最终 Ruff/Black/isort 使用同一源码，不通过删除 fixture 断言处理问题。
文档同步首次拒绝缺少既有关联 owner 文档；仅补齐这些现有文档的合同保持说明，不改映射。
临时诊断 runner 的并行汇总曾覆盖两个索引行，原日志完整保留；按工具实际完成回执和
当时保存的 35 文件计划恢复命令/退出码/耗时，并改为独立命令 receipt 后汇总，未重写旧任务证据。

## Frozen source and actual validation

26 文件名单中 24 个 Python 文件实际改变，另两个保持原字节；唯一项目配置变化为 Ruff
line-length=100。26 文件加 pyproject 的 `git diff --binary --full-index ee3c96e5 -- <scope>`
为 406634 字节，SHA-256
`192dbc631fa9770c18e540261341534e06e42766c3e4851606d43d85d6191582`；逐文件 SHA 在
`logs/python-quality/source-freeze-v2.json`，全部源字节在最终验证期间复核一致。
初始格式 AST 证据、最终函数级非导入 AST 差异分别在 source-after-format.log 与
changed-functions.json；后者列明显式默认值、类型说明、同步捕获、同序短路等人工复核范围，
不把全部后续源码变化误称为逐节点 AST 完全相同。

主任务组织的独立 spec/behavior 和 security/quality 审查均 APPROVE，冻结哈希经主任务
复核一致，无待解决 Critical/Important/Minor；据此获准在必要门完成后本地提交。

| 检查 | 实际结果 | 命令耗时 |
| --- | --- | --- |
| 原 Ruff check，完整 26 文件 | PASS | 0.017s |
| Black --check，完整 26 文件 | PASS | 0.218s |
| isort --check-only，完整 26 文件 | PASS | 0.312s |
| 正常项目配置 mypy，16 生产入口 | FAIL，59 条，与 c24 同配置基线多重集一致 | 7.356s |
| research-web-service-manager | 342 PASS | 7.591s |
| research-web-architecture | 72 JS PASS | 6.204s |
| research-web-local-integrations | 45 PASS / 1 SKIPPED / 1 warning | 19.886s |
| research-web-runtime-mode，修复绑定后重跑 | 322 PASS | 71.174s |
| research-web-installation | 120 PASS | 79.558s |
| project-constraints-local，完整 43 路径 | PASS | 0.161s |
| research-web-docker-contract | 14 JS PASS | 0.240s |
| research-web-container-runtime | 216 PASS | 25.516s |
| research-web-critical-smoke | 20 PASS | 0.588s |
| research-web-verification-full | 100 JS PASS | 5.908s |
| 补充五个已修改测试模块 | 279 PASS | 19.405s |

Python 的 13 个不同测试文件合计 1344 PASS / 1 SKIPPED，未运行真实 Docker Engine 或产品
服务；受控子进程/监听 fixture 不冒充物理验收。JS full 含已列 architecture，去重后为
114 个测试；不能将 72+100+14 当独立数量。实际终端日志纠正了早期进度消息误用旧快照
63/91 的计数。唯一 Python warning 是既有 Starlette/AnyIO 弃用提醒。

43 路径计划包含主任务新写的 `.ai/reports/2026-10-07-ee3-integrated-physical-acceptance.md`；
该文件由主任务拥有，本子任务未编辑，只按明确授权纳入文档门与提交。其物理证据只绑定
ee3，不认证本质量源码；首次 Docker 后续 unknown 及异根方案未在本任务实施。

`logs/python-quality/records.json` 与独立 `record-*.json` 保存真实命令、cwd、退出码、毫秒和
日志引用。最终 12 个 planner 本地门、完整 owner 文档同步与生成索引结果进入本任务新回执；
4 个外部门仍 NOT_RUN，mergeReady/releaseReady=false，host/aggregate 保留 BLOCKED。
mypy 的 59 条既有债务仍明确 FAIL，不因无新增而标 PASS。未发布、未运行 CI、未验证
本质量提交的 Native/Docker 实机、Windows/Linux 或桌面行为。

最终 owner 文档同步实际退出 0（1.126s）；当前 L0 文档治理/索引分别退出 0（0.107s /
0.871s）。现有 schema-v3/v2 validator 实际退出 0（0.038s），valid=true、executedCount=12、
externalCount=4、realMachineCount=0、result=BLOCKED；不改写之前的失败记录或外部门状态。
