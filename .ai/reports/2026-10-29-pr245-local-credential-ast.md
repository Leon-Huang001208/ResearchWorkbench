# PR245 限额后的本地 A/B 候选

宿主macOS；仅本地测试隔离与Host静态验证CPU改进。起点
`38b8227618debc13f67ce02acf73a441aab90395`，各执行owner保存真实WIP文件hash。
没有新branch／task绕过修补限额，没有push、CI重试、PR、merge、安装、部署或真实模型／供应商调用。
原38 Checks45分钟取消／77%且已有E/F、Mac CDN失败及历史凭据UNKNOWN均保留；不由本轮结果回填。

## A：15处显式内存fixture

12个原CI模块：capture_file_alias、source_capture_proof、owned_method_execution、owned_company_policy、
owned_method_compat、owned_method_dedup、owned_method_preparation、pack_execution_host、pack_owned_sources、
pack_source_inputs、pack_ui_projection、scenario_source_selection（均为tests/research_web/test_*.py）。
另3处：test_workbench_operations、test_owned_news_native_sdk、test_execution_cancel_native。
它们显式导入test_api.isolated_keyring，不再假设上游autouse fixture随api别名自动传播。

共享fixture保持function-scope：默认后端与原公共test facade共用本例memory vault，同例MCP签名重开稳定；
退出清内存并恢复monkeypatch。clear继承RESEARCH_CREDENTIAL_HOME及代理键，使用原framework collector
测试开关0；真实系统／文件后端构造、方法和raw keyring入口均拒绝，若异常被上层吞掉，teardown仍拒绝。
不修改任何产品CredentialStore、系统令牌或生产collector默认行为。

外层会话使用真实keyring fail backend，function fixture必须先截住实际构造；原首capture例与scenario
控制例继续走真实Host／Store／HTTPMockTransport／HTTPResponse。测试子进程在Seatbelt deny network*下运行。
没有把T5 inbound-only策略或其精确document case的软件guard泛化批准为Native网络边界。
本地历史测试是否访问／首次创建managed MCP signing token仍UNKNOWN；没有查询Keychain任何secret或metadata。

## B：只在同一fresh AST内枚举一次

唯一产品diff在Catalog.validate：每文件原ast.parse后同try加入局部tuple(ast.walk(tree))，
九个原迭代源换用nodes。原检查、短路、issue顺序和下一文件fresh parse不变；不跨调用／文件缓存，
不合并验证。seed_packages原6次调用、runtime/import-policy、逐次save/fsync/replace、版本、旧结果、
账户及prepare/execute/complete路径均未改。

pre-B的49向量oracle覆盖原26个process别名、允许同名／ThreadPool、相对导入、动态／非批准导入、
安装器、语法／编码、多issue、pack闭包、workflow bindings及method状态；只排除非确定checked_at，
其他返回字段和issues顺序逐项保留。来源是已真实cold初始化后封存的Catalog数据上的真实validate调用，
该纯方法harness不冒充新Host构造；初次harness缺data_root的错误原件单独保留，补正常上下文后才生成oracle。
所有危险脚本是源字节，执行marker始终不存在；改同path字节后再次验证依然拒绝，旧review hash不会复用。

先RED：完整ordered oracle通过，3文件的walk约束观察到24次而非3，故1PASS／1FAIL。
后GREEN：每文件只枚举一次，第二次调用得到新AST；完整oracle及源变化反例均通过。

## 实际本地证据

完整日志／owner／WIP stamps／JUnit位于controller `logs/pr245-local-ab/`。

| 项目 | 实际结果 |
| --- | --- |
| 初始A guard8＋首capture/control | 10PASS，14.44s；unavailable-real层逃逸0 |
| 首F最窄候选＋相邻rollback | 2PASS，0.93s；38 CI首F原因仍UNKNOWN |
| B故意RED | 1PASS／1FAIL，10.57s；49向量oracle已通过 |
| B GREEN | 2PASS，9.41s；49向量、marker、fresh AST反例 |
| 格式后guard8＋B2 | 10PASS，9.60s |
| 最终A guard8（含Protocol keyword）＋首capture/control | 10PASS，11.18s |
| 最后上下文格式修正的guard8 | 8PASS，0.77s；仍无实际系统后端调用 |

上述并发普通功能用时不用于speedup。单独错峰、无Node/API工作进程的正常cold构造各3次，未启用cProfile：

- baseline：4.209267／4.011451／3.981975秒，median4.011451。
- B：3.705113／3.539378／3.605994秒，median3.605994，观测median约下降10.1%。
- 六次均56项、703文件、约20MB，stable checks/status/version/bindings oracle同SHA256
  `62f407f45cc794fb07a10016f9b729cfb758294945afcf807ce8079024465281`。

每个epoch保存Catalog／fixture源码hash、原始时钟与完整oracle，checked_at单列。
baseline后fixture增加了计时外teardown清内存；后继Password keyword兼容不在Catalog的只读get路径执行。
这些WIP差异不隐去。样本仅3次、OS文件cache未清空，不能承诺完整CI时长或据此提高timeout；
先前7.931秒是cProfile，绝未拿它当正常baseline比较。原逐次checkpoint和保留bytes未因本优化减少。

格式／类型工具只复用已安装release Python和现有uv cache，未安装依赖。初始isort/black缺现有tool依赖、
ruff模块找不到binary以及mypy缺ast_serialize的工具错误均留原日志；使用已审完整tool overlay后：

- 正常mypy4个相关源PASS，保留原pyproject/plugin/ignore配置。
- check-untyped-defs候选40条、38原Catalog/API shadow基线41条；去除行号迁移后新增诊断0。
  少的一条是本fixture给values显式dict类型自然消除原var-annotated，非仅行号变化；其余3条Catalog／37条API债务保留。
  这只能称无新增诊断，严格mypy仍BLOCKED，不能称PASS。

ruff／isort／black、Python索引核验、文档治理、研究架构与project constraints最终通过。
README回执原updated值在本地delta没有README变更时先真实失败；修正为本轮unchanged并保留原功能边界后通过，
没有修改checker。完整changed-set Router仍L4／unknown_impact_boundary，未修改策略降级。
机械回执校验valid=true但result=BLOCKED、mergeReady=false、releaseReady=false；其中记录9个选定本地门，
仅3个仓库／文档门PASS，其余原完整范围NOT_RUN，2个外部门因限额冻结BLOCKED。
receipt的level字段按校验器要求绑定选定L4，不表示完整L4已执行或通过。
入口／schema错误的早期回执草稿原件保留；最终相对路径artifact与状态在
`logs/pr245-local-ab-receipt/`，controller亦保留verification-plan-final.json／verification-receipt.json。

## 未执行与发布边界

相关Native7保留NOT_RUN/BLOCKED：尚无本组outer与原inner Seatbelt兼容的test-specific网络边界证明，
没有去掉outer、另造通用父软件guard或冒充运行通过。原Native执行模块／三个driver／两锁／DSH pin的
11份关键文件与38逐字节相同，详见native-byte-reuse-boundary.json；仅两个Native测试文件新增内存fixture导入。
该字节复用事实不能替代新的Native执行验收。

C为ignored单fixture生命周期设计，完整原型执行NOT_RUN；D为fail-fast／预算设计，未改全局pytest hook、
原测试清单、CI参数或timeout。完整7759闭包、新候选安装、模型／供应商、其他平台和独立review未在此充PASS。
三次源码修补限额仍spent3，本地候选不授予第四次远端操作；后继由root决定明确例外与所需硬门。

## 自有临时资源与真实BLOCKED

所有执行根有canonical owner、task/UID/dev/inode/argv与源epoch；原失败日志、baseline/oracle及JUnit在根外保留。
baseline／green两根已归档、实际恢复bytes/type/UID/mode/link相等并核inode/lsof后退役，
归档SHA分别63b2f614f215ae0cc2b25b5473892c9a82c381adf84a0db1ba32f95b905e5bc1、
e0e9b343701b066b37bf0a2dd10a99e07ce6efa701dbbaa5868f5e0deb026754。

A首组收尾在严格symlink mode比较处BLOCKED：
`owned-a-guards-host-1-16df1c88fe9b7ab2`与
`archives/a-guards-host-1/restore-46fceea5b682ebd56a1114b9`均保留，分别50,614,611逻辑字节；
pytest current链接原0755、private-umask恢复副本0700，未把权限意义相近当原mode相等。
完整archive SHA256为0cafe9167000bd29f53dde988a4ac69523a9d2e7014adb9eb5e20567f7ce11b5，
但全量restore比较未通过，不能称恢复PASS。generic helper没有另存新restore创建前inode登记，
这个辅助登记缺口不补造；原test根创建登记完整。
此后已停止清理：收尾快照有8个已登记AB原根及该新副本受保护，后继纯guard重验小根另有owner记录；不改原链接、不follow target、不扩thaw/lchmod。
对象／大小／已验证与未验证范围见resource-blocked-summary.json及archives/*/closeout.json；不称本任务cleaned。
旧50探索根与四个历史提案原根完全保留，没有因当前空间回升删除它们或归功本组。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"产品仅在同次fresh parse后复用局部AST枚举，原检查顺序、依赖freshness、checkpoint、版本与单一DSH边界保持；凭据变化仅function-scope测试fixture，未新增运行引擎、API、权限或服务，原能力图仍准确。","diagrams":[]} -->
