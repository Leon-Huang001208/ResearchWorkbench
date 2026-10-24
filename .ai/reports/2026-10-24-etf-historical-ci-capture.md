# 华安历史验收：CI 输出捕获及封闭后继

宿主macOS，功能缺陷修复；仅本机/同候选Mac安装与通用仓库门。本轮继续用户已确认的华安历史验收生产，Wind Client API仍搁置，定时关闭，AlphaFoundry只读。

## 真实故障与根因

用户确认dee0cce4后主线前进到PR218的b500fcbe。其33个非豁免产品路径与dee0及P3完全相同，只有部署工具、测试和文档变化；历史模式增加既有只读后台空闲门，活动/未知延后。旧dee0 apply在latest门阻断，服务未切换，仍b4384470。

b500只读资格预检又被严格CI ZIP reader拒绝。官方原始归档的0_checks.txt为8,045,256字节，超原8,000,000字节；归档合计8,045,861，其他两个job正常。原始ZIP完整保留在`~/.research-workbench/logs/etf-historical-acceptance-20261024-evidence/pr218-*-raw.zip`，未截断、替换或重打包供认证。

根因是根pytest.ini设置`addopts = -p no:capture`，CI继承后将通过用例的数万条结构化INFO直接输出。原日志42,782行，包含6,620条model_upgrade_checkpoint及大量成功能力初始化日志；不是错误/警告风暴。

## 最小修复与验收

仅在原两条CI pytest命令使用`-o addopts=`恢复标准捕获；模块清单、两次调用、jobs/runner/timeout及所有错误、警告、失败上下文保留。根pytest.ini、产品日志、依赖、8MB/64MB reader与固定reader SHA保持。

任务探针真实执行：同一通过用例打印噪声、同一失败用例打印上下文并记录ERROR、通过用例另发WARNING。原配置与捕获配置均exit1；捕获后仅通过噪声不进入console，失败上下文、ERROR、断言异常及WARNING均保留。结果见`logs/ci-capture/capture-semantics.json`，两份原始输出保留。

新增既有Actions治理合同，先在旧workflow真实失败，修改后整模块通过；禁止恢复capture=no或关闭失败/警告展示。该断言不删减原任何测试。

后继准备：先提交上述完整CI修复为不可变产品祖先，再仅追加新的`reviewed-etf-historical-v2`/`apply-etf-historical-v2`身份，固定前版b4384470并绑定该祖先；旧历史/v8等身份、保全、事务、恢复、reader及严格latest保持。新模式继承后台/Host/Native/私有池/市场空闲门，未知延后，不关闭其他任务。

完整最终候选须普通merge保留产品祖先，经过独立规格/质量评审、Router及原三CI和同候选Mac干净安装。完成后复查精确产品字节仍与用户确认版本一致，再执行原事务部署、真实历史Run与Word/下载。没有正式定稿、模型、Office或供应商实采通过声明。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅恢复原两个pytest调用的标准输出捕获；保留原模块清单和三项CI jobs runner超时及原严格日志reader，不增减验证节点或门禁","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"封闭后继只注册固定前版和CI修复祖先，沿用原Native主实例与私网网关v4事务保全和恢复，没有新服务节点权限或依赖","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"后继沿原全账号档案业务索引与BirthFence维护锁和后台空闲检查，不增加租户共享边界或新的账号数据流","diagrams":[]} -->
