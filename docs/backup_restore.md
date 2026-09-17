# Research Web 备份、恢复与迁移

本页只描述当前 Research Web 的用户数据。旧 PostgreSQL／SQLite 平台的 `backup_db.py`、`restore_db.py`、Alembic 和表责任矩阵保存在 [兼容数据库灾备归档](archive/legacy/database-backup-restore.md)。

## 数据边界

Research Web 的持久数据位于 `~/.research-workbench/`：

| 路径 | 内容 | 是否备份 |
| --- | --- | --- |
| `research-web/` | 会话索引、附件、能力版本、数据集、产物、配置的非秘密部分 | 是 |
| `runtime/dsh/<commit>/` | 可重新构建的固定 DSH 源码与产物 | 否，保留安装清单即可 |
| `run/` | PID、命令指纹和活动进程状态 | 否 |
| `logs/` | 诊断日志 | 按排障需要单独保留 |
| `install/manifest.json` | 安装与依赖摘要 | 建议与备份一起保留 |

模型 Key、数据源密码、Token、Cookie 和其他秘密位于操作系统凭据库，不在上述目录备份或迁移。恢复到新机器后必须在设置页重新授权。

## 旧 Research Web 迁移

先运行只读预检：

```bash
./rwb migrate-research-data --dry-run
```

确认文件数量、大小、哈希和排除项后再复制：

```bash
./rwb migrate-research-data
```

迁移保留会话、附件、能力版本、数据集、产物和原生会话索引，排除凭据、控制令牌、Runtime overlay、临时文件和日志。新实例完成启动、会话读取和文件下载验证后，才可显式使用 `--archive-source` 将旧来源目录改为只读备份。

## 当前目录备份

当前产品没有“在线热备份”命令。需要复制数据根时：

1. 用 `./rwb web status` 确认状态，并在没有活动研究时执行 `./rwb web stop`。
2. 复制整个 `~/.research-workbench/research-web/` 和 `install/manifest.json`，保留权限、文件名和目录结构。
3. 不复制 `run/`，不把系统凭据库导出到仓库或普通归档。
4. 完成复制后可重新 `./rwb web start`。

备份介质、加密、保留期和异地存储属于部署方策略；仓库目前没有自动上传或轮换这些备份的实现。

## 恢复验证

恢复到用户私有目录后至少验证：

1. `./rwb web doctor --json` 不包含阻断级安装或目录错误。
2. `./rwb web start` 后 3081 Runtime 与 8088 Web 均为健康。
3. 历史会话列表、一个附件、一个数据集和一个产物可以读取或下载。
4. 设置页只显示秘密“已配置”状态，不回填秘密值；新机器重新保存所需凭据。
5. Gold／Dollar 框架、能力目录和报告 Workflow 的版本索引可以加载；这只验证恢复，不等于外部来源已重新授权或真实探测通过。

任何恢复演练都应在 `.ai/reports/` 记录实际日期、备份来源、命令、结果、缺失项和恢复用时，不把计划步骤写成已验证。
