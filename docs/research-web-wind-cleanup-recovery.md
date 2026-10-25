# Wind 清理故障：活动观察与恢复边界

本模块是只读诊断和未来事务的私有停止原语。本轮没有恢复执行器、`apply`、`recover` 或 CLI；不修改旧产品 pin、部署 profile、原 `verify_primary`、`Operations.idle`、不可变 `controller.pyz` 或普通停止逻辑。它不能用于恢复当前旧实例。

## Host 的固定观察合同

`GET /api/research/resident` 在 ResearchService 存在时增加 `activity_witness`：

- `schema` 固定为 `resident-activity-v1`；没有账号、文件路径、模型、请求正文、供应商错误或凭据。
- `checks` 固定包含 `research_tasks`、`approvals`、`questions`、`source_requests`、`automation_runs`、`history_jobs`、`sdk_aggregate`、`wind_api`、`market`、`reports`、`datahub_tasks`、`storage`、`asset_directory`、`asset_tasks`、`directory_tasks`。每项为明确布尔值或未知 `null`，每个检查独立执行，已忙或未知均不跳过其他检查。
- `sources` 固定包含 `akshare`、`baostock`、`tinysoft`、`wind`；每项独立报告 `running` 和 `cleanup_unconfirmed`。Wind 在自己的锁内同时观察实际 Future 与 poison，不调用 adapter，不清除 poison、不取消任务。单源异常不会中止其他来源观察，异常正文不进入返回值。

普通 `active` 仍为：任何明确活动返回 `true`；没有已知活动但任一检查未知返回 `null`；全部明确无活动才返回 `false`。Wind poison 仍让原 `source_futures` 抛 `provider_cleanup_unconfirmed`，因此仅 Wind 清理未知时普通 `active=null`，`verify_primary` 与 `Operations.idle` 继续拒绝。分项来源可能晚于旧聚合观察：晚到的实际 Future 将 active 加强为 true，晚到的 cleanup／unknown 在没有已知活动时加强为 null；保留旧聚合调用和 mock 边界，不以旧空闲覆盖新事实。新分项观察不会把它认证为空闲。缺 ResearchService 时继续原返回格式和 `active=null`。

## 只读 inspect

`research_workbench_entrypoint.resident.wind_cleanup_recovery.inspect(home, expected)` 只读取真实安装配置、同 SHA 干净 checkout、真实 `LegacyBinding.discover/verify` 返回的 Host、Native、市场和全部账号（含禁用账号）的持久后台／资产状态。调用者不能填活动观察或 Native 结果。源码状态读取使用 `--no-optional-locks`，不会调用创建目录的 `controller.configured`，不存在的安装不会产生 resident/run 目录。既有部署／BirthFence／恢复 journal 或私有 owner、未知目录、账号数据库 sidecar、活动或未知均拒绝。

唯一接受进一步**观察**的 Host 形态是完整固定 schema、同 SHA、启用 resident、维护标记为 false、普通 `active=null`，Wind `running=false` 且 `cleanup_unconfirmed=true`，其他来源两项均 false，`sdk_aggregate=null` 且其余全部检查严格为 false。旧 Host 缺 schema、Future 未结束、其他未知／混合活动、额外或缺失字段均拒绝，不从日志补证、不注入 flag。

检查复用原全账号 `discovery_background_idle`、`asset_queries_idle`、session/model/file 的原 `snapshot/compare_snapshot` 比较器、完整业务索引及 `@dossiers` 快照范围和 Native 只读查询。独立只读快照组合显式透传 `create_dossier_lock=False`／`create_lock=False`，不调用会按旧默认创建缺失档案锁的 gateway／asset 快照入口；锁缺失或在打开瞬间消失时无 `O_CREAT` 地失败，保留全 home 路径与字节。旧入口默认保持。重复读取可发现观察期间变化，但没有取得三锁或 BirthFence，所以**不是事务准入证明**。返回值始终是 `status=blocked`、`reason=wind_cleanup_controller_upgrade_required`、`ordinary_idle_certified=false`、`recovery_implemented=false`、`transaction_admission=not_run`。快照只返回摘要和账号数，不泄露内容。它不创建恢复 journal、发送信号、启动服务、调用供应商／模型／Office 或改变日程。

档案 WAL 格式（即使正常关闭且暂无 sidecar）及任何 SQLite sidecar 均不属于可安全观察范围，严格 preflight 明确拒绝。受支持的 rollback 字节仅在内存 SQLite 中执行原身份和完整性校验，磁盘上不建立 SQLite 连接，不初始化 wal/shm，也不忽略待回放内容。该限制不会修改原普通部署连接或自动恢复数据库格式。

## 无强杀私有原语

`WebServiceManager._graceful_stop_owned_once` 尚无产品调用者，仅供后续通过完整维护事务审查的操作员使用；不得作为公开停止入口。调用者必须先持安装／生命周期租约、supervisor/admission/operator 三锁、BirthFence 和持久保全事务，并在发送前持久记录信号意图。原语强制接收同一真实安装租约，在入口、持久回调之后／信号之前及每轮等待调用原 `_assert_installation_scope` 校验；缺租约或租约失效时拒绝。三锁、BirthFence 和维护事务仍须后续完整执行器提供，不能仅凭该租约认证。原语连续验证 PID 出生时间、完整 argv、原 state 签名和监听者，仅发送一次单 PID `SIGTERM`；持久回调之后再次验证，PID 复用／命令或监听变化立即拒绝。

已记录意图的显式恢复必须传 `signal_already_attempted=true`，只等待退休，不重发。意图落盘后、信号发送前崩溃存在不可消除的歧义，此时也不能重发；需保持事务阻断。超时、信号异常、未知身份均返回明确错误，不升级 `SIGKILL`、不调用 `killpg`、旧 `_stop_owned_probe/_stop_locked/restart` 或回滚，不删除 state／认证，不自动启动。原普通 stop 的十秒后强杀后备保持原合同，不能用于此维护恢复。

## 完整恢复仍未实现

旧已部署 `controller.pyz` 不认识独立 Wind 恢复 journal。只修改新源码 controller 的 guard 无法阻止旧监督器自动 ensure/recover；伪造旧 `transaction.json`、暗改 controller/hash 或宽泛允许 unknown 都不能闭合该边界。因此完整可恢复事务为 `NOT_IMPLEMENTED/BLOCKED`。后续需要单独审查并受控交付可识别新事务的 controller 兼容合同，再实现三锁／BirthFence、固定安装与端口身份、全账号保全、一次信号阶段恢复、旧 PID 退休／端口空闲后同版启动及普通真实后验校验。没有这些证据前不能提供 apply 或宣称可恢复。

当前旧 b800 Host 无分项见证，必须保持拒绝。新源码和离线测试不会给旧进程补出证据，也不构成实际部署或现场恢复许可。既有 Run、工作簿、Excel/Wind、模型、账号、旧报告及关闭的日程继续保护。

## 离线验证

相关测试为 `test_wind_recovery_activity.py`、`test_wind_cleanup_recovery.py`、`test_service_manager_graceful.py`，与原 `test_resident.py`、`test_datahub_wind.py`、`test_datahub_reliability.py`、`test_service_manager.py` 一起回归。测试禁止真实 Office 构造；供应商、模型、安装、常驻更新和真实停机均不执行。临时 Git／SQLite／真实 LegacyBinding 合同测试与模拟 OS 进程事实分别覆盖，不能替代 macOS 真实恢复事务、CI 或未来部署验收。
