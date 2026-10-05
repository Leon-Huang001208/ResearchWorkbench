# Native / Docker 双运行时：Task 12 文档与架构回执

## 范围

本任务只更新当前产品入口、安装/运行说明、架构清单、部署图及文档契约测试；Task 1–11 的实现、隔离分支和审查证据保留。没有安装依赖或运行时，没有修改全局 Hook、manifest、插件缓存和信任配置，也没有推送或发布。

README 把 Docker 列为新安装推荐入口，同时明确 `--runtime` 无参数继续选择 Native。安装指南分开记录模式切换、共用研究数据、分离状态/凭据、稳定 issue code、修复与非破坏性卸载。Windows `.cmd` 是接口说明，不是实机 Docker 生命周期验收。

## 文档契约与部署图

先增加两项文档/架构契约测试，再运行 RED：`node --test tests/javascript/documentation_governance.test.mjs tests/javascript/research_web_architecture.test.mjs`，71 项中 69 通过，两个新断言按预期失败（README 缺双运行时入口；map 缺新的运行合同）。文档和图源更新后同一套测试通过 71/71。

`01-deployment` 图源显示一个源码/锁定依赖合同、Native Web/DSH 两宿主进程、Docker 单容器、顺序共用研究数据及分离凭据/状态。Archify showcase validate 9/9、0 error、0 warning；deliver 图源 SHA-256 为 `94c6eaa9a365b3fee1d7a481742f21d0dd4c962311f18721e1118ae990c10def`，HTML 为 `400f75c7067b30c1fc5d284b65461787234a8071d45446cd8a2594e666cdd0c9`。首次受限环境的 visual-check 因 Chrome 在测量前退出而失败；对同一命令获窄范围许可后四视口包含性、明暗截图均通过。人工查看最终哈希的 1440 浅色与 2048 深色截图，未见遮挡、节点穿线或裁剪；图形不证明产品或 Docker 真实生命周期。

## Task 12 本地门禁

| 实际命令/范围 | 结果 |
| --- | --- |
| `node scripts/check_documentation_governance.mjs --project .` | 515 份 Markdown，0 violation |
| `node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs` | 83/83 通过 |
| `/opt/homebrew/bin/python3.12 scripts/generate_py_file_index.py --check` | 生成索引已校验 |
| `node .agents/project-constraints.mjs`，传入 Git 对 HEAD 的全部 25 个本轮已改/新增文件 | 0 violation |
| `git diff --check` | 通过 |

任务书中仅传 `README.md`、安装文档、`Dockerfile`、`process_spec.py` 的示例命令并非完整 changed set，按门禁设计会因未列入已更新的 README receipt、模块文档和架构报告而报 7 项 `not_changed`/`review_invalid`；这不是文件内容失败。改用实际 25 文件集合后为 0 violation。只读规划器对此 25 文件集合给出 L4，因为 HTML/截图回执和两个测试路径在现有策略中归类 `unknown_path`；其本地 L0 与 L4 命令如上已执行，外部 `project-constraints` 尚未运行。Task 13 将基于原目标的完整分支 changed set 另行规划，不把本轮局部结果冒充整体验收。

<!-- architecture-review {"group":"dual-runtime","structure":"changed","reason":"新增模式路由、固定运行合同与 Docker 单容器部署，改变部署拓扑及数据/状态/凭据边界。","diagrams":["01-deployment"]} -->

## 未验证与后续门

- 本任务没有运行真实 Native/Docker 安装、镜像构建、服务切换、Windows 或外部 CI；不得据此宣称平台通过。Task 13/14 按完整 changed set 与实际授权单独执行必要验收和外部门。
- Docker 真实镜像构建此前受外部 APT 网络失败阻断；当前 Windows Docker 凭据 ACL 无可证安全路径时以 `docker_credentials_acl_unverified` 失败关闭。
- 本轮只读诊断确认 Harness runtime 后来已一致，但**更新执行者未知**；没有证据证明自动修复，本任务不追查更新者，除非再次出现异常写入或漂移。
