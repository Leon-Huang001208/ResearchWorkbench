# PR245 CI 安装漂移与旧 fixture 修复

- 平台／范围：macOS 本机，CI／测试修复；app 源码、approved web.lock、runtime lock、身份及权限门未变。
- architecture-review：原 Host／唯一 DSH 和运行依赖冻结链保持，无新引擎、API、依赖、job、runner 或 timeout。
- 起点：8effbf5b1ba323e9bd6d1ea58c9ba2707e67d379；原 CI checkout b4bf3af9dc0d03f2599ba26eac20ef2bb8a41dd2。

## 原始失败与根因

Checks 40608520536（job122553986917）690.05 秒：198 failed、7087 passed、101 skipped、373 errors、133 subtests。原无约束 editable dev 安装将 rpds-py 装为2026.9.1（期望2026.6.3），idna 装为3.20（期望3.19）；其余五分发与投影一致。runtime 全七项为 jsonschema4.26.0、jsonschema-specifications2025.9.1、attrs26.1.0、referencing0.37.0、rpds-py2026.6.3、typing-extensions4.16.0、idna3.19。web.lock SHA256 为7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102，未修改。

另一个独立 fixture 在真实 ResearchService._data_query_admission 调用新增 validator 时抛 AttributeError。本机编辑前定点复现1 failed/0.61秒；原件与原 CI 全日志均保留。

## 最小修复

原 Install heredoc 校验 whole-lock SHA、投影 schema、唯一条目、版本和 hash，从原锁生成七 runtime＋原三 renderer 的哈希 requirement 与纯版本 constraints。先原哈希安装，再原 editable dev 安装约束，最后逐项 metadata 核验七 runtime。错误写 logs/ci-pack-dependencies.log 并抛出；没有降级身份校验。

旧 fixture 绑定真实 ResearchService._validate_data_query_scope，提供实际 financials 声明和有期限／配置绑定的合成健康 probe，沿真实 admission_catalog／data_preflight 执行。保留成功证据和单次 readiness 断言；撤销声明后明确拒绝 data_outside_declared_scope、清除执行证据并验证不重入。真实供应商／模型未调用。

治理测试执行 workflow 中真实两个 heredoc：成功、SHA错误、缺包、重复、版本错、缺hash以及逐七项实装漂移拒绝；不只检查字符串。

## 实际验证

证据目录：CONTROL/logs/pr245-ci-repair/（CONTROL 为任务既有隔离控制仓库）。

- fixture-red.log：原 AttributeError，1 failed，0.61秒；归档恢复逐文件hash相等、原dev/inode及lsof复查后仅清理自有根。
- fixture-green.log：首次新增真实声明暴露未提供健康probe的fixture问题，1 failed、12 passed；保留未覆盖。
- fixture-green2.log：完整模块13 passed，0.58秒；成功／真实拒绝及不重入均通过。
- runtime-green.log：投影真实runtime identity和错误投影拒绝，2 passed，0.31秒。pytest current绝对symlink导致首次归档提取拒绝；随后逐成员路径／链接限定自有root，实际恢复并比较文件hash及链接原值，原inode／lsof复查后只回收自有目录，见runtime-green-recovery.json。
- governance-green.log：Node24.19，21 passed、0 failure/skip，455.25毫秒（含上述真实heredoc矩阵）。
- 无本机pip安装；pytest和formatter仅从已批准release环境及既有cache只读加载。初始工具cache缺mypy_extensions及ruff binary定位错误保留诊断，随后使用已有明确路径，不安装包、不改PATH。

原 Mac Bootstrap 与 Constraints 对旧候选通过，不能用于本候选。新候选三CI、同候选Mac干净安装、独评及整轮交付由主任务继续；此报告不宣称新CI通过。Windows/Linux产品、真实模型质量、部署保持NOT_RUN。公开仓库资格与预算由主任务发布前实时核查。未触常驻服务、凭据、业务数据、原Desktop Git或其他任务资源。


<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks安装步骤对齐已有冻结分发并修复旧测试夹具；原CI作业、唯一DSH、Host权限和架构图拓扑保持不变","diagrams":[]} -->


## 最终本地完整性与工具状态

- Black26.10.1 `--check`、isort9.0.2 `--check-only`、Ruff0.17.0 `check`：变更fixture均通过；原有cache路径、METADATA SHA及源码树SHA记录于toolchain.json。
- mypy2.4.0 `--follow-imports=silent`：TOOL_ERROR；同版本对干净8eff fixture做`--shadow-file`基线重跑也INTERNAL ERROR，trace定位缺少既有cache依赖ast_serialize。未安装包、未关闭插件／ignore／减门；不能声称类型检查PASS。
- 原Constraints的四Node模块：114 passed、0 failure/skip，4.78秒，constraints-node.log。
- `scripts/check_research_architecture.mjs --base 8effbf5b1ba323e9bd6d1ea58c9ba2707e67d379`、`scripts/check_doc_sync.py --base ...`、`scripts/check_documentation_governance.mjs --project .`、`scripts/generate_py_file_index.py --check`、九项显式changed-file的`.agents/project-constraints.mjs`：通过（原完整性RED要求三份workflow模块文档与结构决策，补齐后GREEN，不更改规则）。
- `git diff --check`：通过。app／锁文件没有diff。仅本任务临时测试根已按原身份、归档恢复hash和lsof校验清理；证据及工具cache保留。磁盘剩余约3.41GiB，未触碰他任务资源。最终localcommit与新候选CI由主任务回执绑定。

实际命令入口：指定release Python执行pytest（explicit confcutdir/basetemp，小组≤13项），Node24.19执行actions_quota_governance和原Constraints四Node模块；formatter用指定cache PYTHONPATH或ruff已存在binary，未全局改PATH。完整argv及candidate在fixture-red/fixture-green2/runtime-green归档owner和对应JSON中。
