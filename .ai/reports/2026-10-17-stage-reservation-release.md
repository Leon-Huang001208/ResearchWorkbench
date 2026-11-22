# stage 预留保全释放

宿主 macOS，管理员生命周期修复；Mac Docker Desktop 验收。原 Hot 任务 hot-periodic-docker-projection-20261015 的 PR114 已合并，continuation 最终回执确认 Mac 完成、句柄终态及 stage 停止。原任务因 Git 身份拒绝保留工作树和证据，本任务不清理它们。

原 manager stop 不退休预留，stage 2 GiB 账本永久占满池。新增显式 release-reservation，仅接受 stage 和精确 CID/image/source、已完成任务标识。沿原 operation.lock 及容器/卷/网络/限额归属检查，拒绝运行中、共享卷及身份变化。原账本先私有归档回读，然后退休预留；不停止或删除容器、网络、卷，不读取秘密内容。新任务必须独立实例与新卷。重复请求拒绝，不重复归档。

本地 Python 闭包269项、最终manager专项37项、Node130项与ruff/文档/索引/完整改动约束通过，独立Python评审无剩余阻断。CLI测试首次capsys夹具错误保留，改为真实子进程验证后通过。真实受管释放成功，原CID/镜像/挂载/启动时间及五卷投影均不变，两个运行中容器相同；原账本归档回读。原始证据位于 /Users/leon/.codex/automations/dsh-fork/evidence/stage-release-20261017/，源代码PR/CI仍待执行。Windows/Linux 原生任务及 dispatch 由对应设备负责。此修复不部署产品或更新常驻服务。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"管理员账本新增显式退休动作，复用原操作锁和身份检查，保留全部容器卷，不增加研究引擎或部署通道。","diagrams":[]} -->
