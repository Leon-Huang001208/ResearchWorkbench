# Mac mini 空私有池网关升级

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

失败恢复旧网关源码和与当前主实例匹配的绑定；原失配配置另留审计，不能当作健康回滚。恢复先写 rolling_back 再切源码与配置；preparing 阶段崩溃只撤销本事务空槽，不发信号。恢复不覆盖业务文件或凭据。独立不可变 recovery.pyz 和 LaunchAgent 在停机前安装，崩溃后按同一 journal 恢复；活动、身份不符或状态不明仍延后。

证据在私有 `server/run/gateway-upgrade-{original,result}.json` 和 `logs/gateway-upgrade.log`。不记录问题或回答正文，不触发模型调用。源码、模拟测试、CI和真实部署结果分别报告。
