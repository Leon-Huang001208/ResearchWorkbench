# Mac mini 空私有池网关升级

## 保留主实例版本的静态网关更新

主实例无需更新研究进程时，显式使用 `apply-ui --preserve-primary`，`--primary` 固定实际主实例 SHA，
`--target` 固定已合并、资格通过的新网关 SHA，`--expected-gateway` 固定旧网关 SHA。
这与默认 `apply-ui` 的 primary=target 合同分开；不扩大自动兼容白名单，不安装或切换主实例。

注意：主账号的 `/` 和 `/static/*` 仍取自主实例的 UI 目录，因此此模式不能单独交付主账号的侧栏等完整壳更新。
需要完整更新主账号界面时，应先使用下节 `stage-primary-ui`，由原 resident 完成受控切换，再更新网关；
不能把网关 revision 更新或旧菜单适配当作主账号已加载新侧栏的证明。

version 3 / `static-gateway` 事务同时检查 primary→target、旧网关→target、target→tool 的祖先和完整 blob。
前两段仅允许 UI、文档、测试、报告和确切的升级器模块；升级器 blob 必须等于经过资格认证并冻结的工具 blob。
最后一段只允许升级器模块、文档、测试和报告。后端、依赖、控制器或任何未知路径变化均拒绝。
升级器是显式操作员模块，业务运行时不导入它；上述合同保证运行时后端保持一致。

恢复包支持独立的 version 3 身份、三段离线 blob 验证和原主实例 SHA；v1/v2 helper 不接管 v3 journal。
原锁、空闲/私有池检查、恢复包先安装、优雅排空、保全和回滚均继续执行。工具与目标资格均独立核对。
旧主实例的已有菜单由网关适配身份链接，复用原交互控制器，避免重复菜单或重复退出监听。

## 显式准备主实例 UI 候选

当已合并的 UI 更新同时包含本升级器自身时，自动 resident 仍拒绝该路径。先从精确目标的干净工具 checkout、使用原主实例解释器执行：

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.gateway_upgrade stage-primary-ui \
  --home /absolute/private-home --source /absolute/reviewed-target-checkout \
  --primary EXACT_CURRENT_PRIMARY_SHA --target EXACT_VERIFIED_MASTER_SHA
```

此命令只准备新旧 wheel 和私有 candidate，不停服务、不更改自动白名单、baseline 或 controller.pyz。
它核对同一 Git common directory、工具实际路径、解释器、原 manifest 与源码、隔离候选、最新主线及原三项 CI；
拒绝 primary/gateway 恢复 journal、其他任务尚未接受的候选和准备期间的候选替换。
只允许 UI、文档、测试、报告及本升级器一个精确 Git blob；已有已接受的旧候选可退休，同一审查身份可重复校验。

随后执行原 `rwb resident tick`（或等待已安装监督器）：原不可变控制器仍持准入/lifecycle锁、检查原生/Host/排队自动化空闲，
写 journal 后才切换，失败仍恢复旧 wheel 与源码。必须确认 accepted、实际进程 revision 和会话/模型保全后，才能继续下述网关 `apply-ui`。
主实例已到目标时跳过准备；活动或未知保持 deferred，不强停。现场不可变控制器须先独立核对支持复用同一 previous/target candidate。

## 已验收界面的显式更新

当主实例已自动更新而网关仍使用旧界面时，用`apply-ui`更新网关。工具版本与产品版本分开认证：
工具checkout须为最新已合并、独立评审及三CI通过的提交；`target`须等于当前primary且独立通过原资格核对。
旧网关到产品只允许UI、文档、测试与报告；产品到工具只允许升级器自身及文档、测试、报告。
两段差异均核祖先和完整路径/blob，禁止用rename隐藏后端删除；依赖、未知后端及控制器变化拒绝。

产品段也可包含本升级器自身，但其完整 Git blob 必须与冻结工具版本中的同一路径完全相同；
不接受缺失/删除或与恢复工具不一致的 helper。该判断随 version 2 恢复包冻结，离线恢复再次执行同一校验，
不会把一段临时内存放行逻辑冒充持久恢复合同。

```bash
/absolute/primary/.venv/bin/python -m research_workbench_entrypoint.resident.gateway_upgrade apply-ui \
  --home /absolute/private-home --source /absolute/reviewed-tool-checkout \
  --expected-gateway EXACT_OLD_GATEWAY_SHA --primary EXACT_CURRENT_PRIMARY_SHA \
  --target EXACT_CURRENT_PRIMARY_SHA
```

命令须从已审工具checkout运行；业务网关只切换到产品target，工具源码不写入主实例或业务checkout。
自动兼容白名单、既有控制器与version 1/固定旧primary恢复合同保持。新模式使用version 2 journal，
记录两份资格证明、逐路径blob及工具身份；旧helper在任何进程/源码/配置/slot操作前拒绝version 2。

新版恢复pyz从工具Git对象构建，使用内容寻址路径与独立LaunchAgent，不覆盖旧artifact/job。
恢复核对自身身份、manifest/Git blob、目录和共同Git身份、两段离线差异及实际primary；不要求在线GitHub，
也不依赖工具checkout继续存在。当前master、其产品/网关祖先及不可变恢复包在事务结束前必须保留。
恢复成功后仍只回退网关源码和匹配绑定，不回写会话、附件或模型设置。

全部原supervisor/admission锁、出生栅栏、SIGTERM身份/排空、完整保全及journal先落盘的门继续执行。
发信号前活动/未知返回`deferred`；发信号后尚未退休或恢复未完成返回`recovery_required`并保留journal，
不能当作部署成功，也不得升级到强杀。

## 既有管理平面专项

这是显式操作员入口，不扩大 resident 自动兼容清单，也不修改原 controller.pyz、安装基线、主实例 wheel 或研究引擎。当前受审产品基线固定为 `6c4ac79bcf03fb36ffbe9c1c40a647b8e8a34556`；目标相对此基线只接受列出的管理平面源码及文档、测试。其他产品变化必须重新专项审查。

```bash
python -m research_workbench_entrypoint.resident.gateway_upgrade apply \
  --home /absolute/private-home --source /absolute/reviewed-checkout \
  --primary 6c4ac79bcf03fb36ffbe9c1c40a647b8e8a34556 --target EXACT_MERGED_SHA
python -m research_workbench_entrypoint.resident.gateway_upgrade status --home /absolute/private-home
```

`apply` 校验同一 Git common directory、干净源码、最新 merged master、受管独立评审和三项实际树匹配的 CI。主实例 supervisor/admission 独占锁覆盖整个操作；Native、Host、自动化任一活动或未知都延后。任何私有 owner、auth/key、未知控制记录、相关子进程或孤儿进程也延后，不强停研究。

首次升级持 SQLite `BEGIN EXCLUSIVE`（仅查询、最终 rollback），覆盖全部账号且拒绝 WAL/hot journal；对每个空 owner 槽位先登记暂存目录 inode，再用 macOS `renamex_np(RENAME_EXCL)` 原子占槽。已有原生 owner 永不覆盖。出生栅栏不能代替 HTTP 排空。

普通 SIGTERM 等待 uvicorn 完成已接纳请求和线程；超时保留 journal，不升级为 SIGKILL。重复信号只允许经过版本、handler 源码摘要及默认无强制超时合同核验的 uvicorn 0.53.0；未知版本拒绝。旧 PID 完全退出后才移除 launchd job；KeepAlive 替代进程不能穿过仍持有的 SQLite 锁。

目标网关在 `server/run/gateway-upgrade.json` 存在时拦截全部业务 GET、登录及控制请求，只开放廉价健康端点。排空后才释放旧出生栅栏，再启动冻结目标。目标健康、当前 primary 绑定和会话/模型配置/账号库保全全部通过后才移除 journal。

SIGTERM后只以PID消失确认退休；zombie或签名变化继续等待且不追加信号，超时延后。完整保全journal专属上限16 MB，发首个信号前核对实际JSON UTF-8字节并预留4096字节phase余量；专属reader以同一私有fd核对身份、长度、时间及当前路径，拒绝替换、短读或超限。配置通用reader仍为1 MB。

失败恢复旧网关源码和与当前主实例匹配的绑定；原失配配置另留审计，不能当作健康回滚。恢复先写 rolling_back 再切源码与配置；preparing 阶段崩溃只撤销本事务空槽，不发信号。恢复不覆盖业务文件或凭据。独立不可变 recovery.pyz 和 LaunchAgent 在停机前安装，崩溃后按同一 journal 恢复；活动、身份不符或状态不明仍延后。

证据在私有 `server/run/gateway-upgrade-{original,result}.json` 和 `logs/gateway-upgrade.log`。不记录问题或回答正文，不触发模型调用。源码、模拟测试、CI和真实部署结果分别报告。
