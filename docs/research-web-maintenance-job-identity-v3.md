# 受控维护的精确作业身份 v3

`research_workbench_entrypoint/resident/maintenance_job_identity_v3.py` 提供
`ExactJobBinding`。它只描述并重验目标，不是执行权限，不注册、停用、启动、终止或恢复
launchd 作业，也不申请端口。普通研究 HTTP、模型输出及任意 JSON 不能由此取得系统权限。
实际效果仍须由原维护上下文、真实锁、预算准入和持久 intent 授权。

## 固定生产目标

`ExactJobBinding.production(home=...)` 只接受当前用户的
`~/.research-workbench`。它只读现有 `server/resident.json`，要求明确整数端口 8089；
不以缺失字段推导默认值。label 固定为 `com.research-workbench.multiuser-server`，
plist 固定在当前用户 `Library/LaunchAgents`，domain 固定为实际 UID 的 GUI domain。
目录、配置字节与身份发生变化时，原 binding 失效。

这个描述可用于定位旧实例，但不证明旧作业的完整已加载策略、空闲、清理成功或回滚资格。
生产 binding 不自行声明脚本、解释器或 registration nonce 已获认证。

## 已登记的私有演练目标

受控操作员先准备归自己所有的 0700 根与 `LaunchAgents` 子目录，以及 0600 控制记录
`maintenance-job-identity-v3.json`。根不得位于生产数据或真实 LaunchAgents 目录内，
也不能成为这些目录的祖先。工厂不创建目录、登记文件或 plist。

记录只有以下字段，重复键、额外字段、非有限 JSON、错误 UID/目录身份或格式均拒绝：

```json
{
  "schema": "rwb-maintenance-job-identity-v3",
  "task_id": "approved-maintenance-task",
  "owner_uid": 501,
  "nonce": "00000000-0000-4000-8000-000000000001",
  "root": "/private/tmp/approved-private-root",
  "root_identity": [16777234, 123456],
  "script": "/private/tmp/approved-private-root/entry.py",
  "script_sha256": "<64 lowercase hex characters>",
  "executable": "/approved/venv/bin/python",
  "executable_sha256": "<64 lowercase hex characters>",
  "port": 54031
}
```

示例的 UID、路径、inode、nonce、端口和摘要均须由实际已审计划取得，不能照抄。
调用 `ExactJobBinding.rehearsal` 时，分别传入 `root/task_id/nonce/script/executable/
script_sha256/executable_sha256/port`，与登记文件及真实文件交叉核对。
两个摘要均为必需的独立已审输入；不得只接受登记文件自报的摘要。

label 唯一派生为 `com.research-workbench.maintenance-rehearsal.<nonce.hex>`；
调用者不能自选任意系统 label、domain 或 plist 路径。端口仅接受已登记的 49152–65535
整数，排除生产的 3081/8088/8089。端口是否已准入、是否仍可用、实际 listener 是否归属
当前尝试，仍须由执行器在效果前独立证明；binding 不声称持有端口。

## 重验与消费者责任

公开字段包括 `scope/home/label/domain/plist_path/port/script/executable/nonce/task_id`、
两个 artifact 摘要以及 `identity_sha256`。`verify()` 重读原登记及 artifact，检查目录、
原 inode、权限、硬链接、内容、解释器引用和目标替换；失败只抛稳定 `UpdateBlocked` 代码。
对象不可变，不能用 `dataclasses.replace` 改目标后继续通过原重验。

全部摘要读取后再次 no-follow 核对每份原件的完整 stat 身份，拒绝后读取的解释器校验期间
先前脚本／登记被写入。这个检查不提供跨文件原子快照，也不持有生命周期锁；消费者须在
真实维护上下文保护下于效果前重验，不能把一次只读观察当作持续隔离。

- 登记/配置读取上限 64 KiB，脚本 1 MiB，解释器 256 MiB；分块读取，拒绝 FIFO 与异常文件。
- 私有控制文件须为 0600 单链接普通文件，脚本仅接受 0600/0700；目录逐级 no-follow。
- 已审解释器的叶级 venv 符号链接保留为实际 argv，并分别固定链接及解析后二进制。
  不将 venv 路径替换成系统 Python。依赖及完整候选闭包仍由维护上下文验证。
- plist 可尚未创建；若已存在，必须为安全的同用户单链接普通文件。
  binding 不封印 plist 内容，也不把磁盘 plist 当作已加载策略；消费者仍须独立核对。
- UID、文件权限和内部发行标记不构成对恶意同进程 Python 的隔离，更不替代人工授权。
- 全部 probe、load、stop、restore 必须消费同一个完整 binding，包括端口；不得改了
  label 却继续探测生产 8089，或用全局 LABEL 替换/模拟结果取得现场资格。

实际私有 launchd 演练应先形成唯一 label、脚本、路径、端口、有限寿命、原 disabled
三态及清理/回滚清单。若原态为 UNSPECIFIED，不能把 `enable` 后的显式 false 宣称为
精确恢复；不得对整个 GUI domain 执行 `reset-disabled`。本模块不执行这些操作。

合同测试是 POSIX 文件与数据合同证据，不是 macOS launchd、完整 CLI、生产者排空、
旧实例退役、Wind/Office 保全、部署或 Windows/Linux 原生产品验收。历史 UNKNOWN 账本
继续保留；新 binding 不得追补旧进程的清理或加载策略证明。
