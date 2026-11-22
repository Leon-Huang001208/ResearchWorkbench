# B1复SPEC修波2：历史只读保留runtime freeze门

base `6d782ab6fec344a4e6de6749f2e65c2bc2023904`；任务seek-packs-20261027-7bda5752。
macOS Mac mini Web功能修复，独立worktree，仅本地scope commit回root复SPEC→Python／TS。
不改UI／140映射、A6纯核／baseline／contracts、既有证书／审计schemas或旧三参执行门。
无新依赖／真实模型／供应商／生产服务／部署／push。

## Important与最小修复

专用历史pack reader使用当前等价records直接进入无写声明helper时，漏掉普通
`_data_query_admission`入口的`plugin_runtime_frozen`门。真实合法证历史fixture可复现读取
在服务冻结时仍返回raw。不能靠HTTP/tenant中间件覆盖内部／已进入请求，也不能重开严格
旧version执行门而破坏已完成的只读等价路径。

先加freeze-before、_verify_raw期间开启freeze、直接专用adapter入口和原三参callback对照：
RED **3 failed**／25.35s；未把原门的拒绝当新路径正确。增加单一固定错误的freeze检查：
只有已识别pack的records入口/返回及snapshot adapter入口/结束检查runtime标志，既有raw后
adapter复验因此再次执行同门。普通非pack来源只读的原行为不扩大。Dossier仅保留该稳定
`plugin_runtime_frozen`409错误码，不包装成证据缺失，不捕获降级／不加公开bypass字段。
定点GREEN **3 passed**／25.04s（1原Starlette warning）；实际内部非tenant方法调用，没有
mock准入passed，source权限和当前version/证书/raw链仍真实。

## 验证与资源

相关闭包范围：完整历史/迁移读取、输出审计39字段反例、旧Dossier/保全、原capabilities
admission/旧场景；精确argv/env/PID/UID、实际duration和log sha由
`logs/research-packs-b1-freezefix-20261027-73e819/final-python-receipt.json`保留，结果追加后再记通过。
局部绿色不等于九包来源完整、正式报告质量、真实模型或生产上线通过。

本波仅explicit `rwb-b1-freeze-fix-73e819-*`与final runner随机basetemp，原runner仅归档hash
读回后清理自身final temp；旧50根归属/处置仍由root处理，本worker不再扫描或删除/tmp。
工作树/必要日志保留独评。Mypy仍缺librt未执行；UI/140、平台原生、CI、生产模型/供应商/
服务/部署仍NOT_RUN，未用静态pin白名单冒充模型工具选择或真实源质量。

## 最终本地回执

相关闭包实际 **177 passed, 1 warning in 374.83s**，runner duration375.068s，runner PID7823／
pytest PID7825／UID501。日志SHA256
`24ba8b0b77271844404513d870778b21eb01b780f4d01a71094424b6dc62d606`；回执SHA256
`c4f21fbf6a4167444972bc9f8f795319e40a7dbb1c673d816044728c6e123954`。
final runner保留38份full-result证据并逐hash读回后仅清理自己final temp，`temp_cleaned:true`。
定点RED/GREEN的explicit basetemp与日志仍保留，未将旧探索资源混入本次清理。
Ruff、Black3files、isort、pyindex `--check`、`git diff --check`实际通过；对A6 commit的
scenarios/packs、baseline.json、contracts.json执行`git diff --exit-code`通过，冻结字节未变。
本波未改JS，未重跑此前37项Node；独立复SPEC及Python／TS审核仍待root执行，局部修复不冒充整体交付。
