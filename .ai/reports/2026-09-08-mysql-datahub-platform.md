# 用户自配置 MySQL DataHub 交付报告

**任务 ID**：`aliyun-datahub-provider`  
**日期**：2026-09-08  
**状态**：Web 实现与 macOS 本机模拟验收完成；真实 MySQL 及非 macOS Web 凭据库验证待执行

## 交付范围

- 新增通用 `mysql` DataHub Provider。连接非秘密字段原子保存到本机 `RESEARCH_DATA_HOME/connections/mysql.json`，密码只进入系统凭据库。
- 新增 MySQL 配置 GET、PUT、DELETE API；API 不返回密码，只返回 `secret_configured` 等安全状态。
- 新增 `datahub_get_database_schema` 与 `datahub_query_table`，并把 DataHub 目录扩展到 15 项能力、22 个来源。
- 查询仅允许经过严格校验的单表、显式列和参数化过滤；每次连接执行权限检查、只读事务，并在结束时回滚与关闭。
- 新增设置页“连接与授权”、DataHub 四阶段状态链和移动端 44px 控件约束。
- 新增内置 Skill `factor-database-research` 及 BP 十分位示例；不提供绕过 DataHub 的直连数据库脚本。
- 更新 Research Web 架构、DataHub、UI、能力目录和变更日志文档，并重新生成受影响的架构图与视觉凭据。

## 安全边界

- 未使用或提交对话中出现过的旧主机、账号或口令。
- 凭据库失败时返回 `credential_store_unavailable`，不降级到环境变量或明文文件。
- `required_no_verify` 使用显式 TLS context，禁止降级到非 TLS，并在来源与快照中保留 `tls_certificate_unverified` 警示。
- Manifest 只使用 `mysql://database/table`，不包含真实主机、用户名或密码。
- 已有会话快照在删除连接后继续可读；配置变更不级联删除历史数据。

## 实际验证

| 检查 | 结果 |
| --- | --- |
| `LOG_LEVEL=CRITICAL .venv/bin/python -m pytest tests/research_web --confcutdir=tests/research_web -q --tb=short` | 460 passed，3 skipped，1 个第三方弃用警告 |
| `node --test tests/javascript/research_web*.test.mjs` | 166 passed，1 skipped |
| `node tests/e2e/research_web_mysql_configuration.mjs` | 8 个主题/视口组合通过；未连接真实数据库或模型 |
| `python -m ruff check app/research_web tests/research_web` | 通过 |
| 针对新增文件的 `black --check` 与 `isort --check-only` | 通过 |
| 针对 8 个变更 Python 模块的 mypy（Python 3.12） | 通过，0 issues |
| `node scripts/check_research_architecture.mjs` | 通过，0 violations |
| 架构图 Archify 交付与多视口明暗主题视觉检查 | 3 张受影响架构图通过，showcase 0 errors / 0 warnings |
| `git diff --check` | 通过 |

完整 Python 回归曾稳定暴露一个既有异步测试只等待 0.5 秒的问题；单测连续三次通过但完整套件连续两次停在 `preparing_data`。将测试等待上限改为 5 秒（目标状态出现即提前结束）后，完整回归通过，未修改报表运行逻辑。

## 浏览器验收

- 视口：390×844、768×1024、1280×720、1440×900。
- 主题：每个视口覆盖 light 与 dark。
- 覆盖：密码不回填、提交后立即清空、留空保留旧密码、保存/删除、DataHub 状态链、检测反馈、无横向溢出和移动端触控尺寸。
- 证据：`outputs/research-web-mysql-acceptance/receipt.json` 与同目录 16 张截图。

## 未验证项与剩余风险

- 未连接真实 MySQL。真实验收前必须轮换对话中出现过的旧口令，并使用只含获准投研数据的只读账号。
- 未执行 Windows/Linux 上的 Research Web 系统凭据库验证；macOS 本机结果不能证明这些操作系统的 Keyring 后端兼容。
- 桌面 sidecar、Tauri 安装包与桌面安装级冒烟已按用户确认排除在本次范围外。
- 未执行真实模型调用。保存配置后可立即探测，但 DSH 中的两个新工具需要重启研究服务后重新物化。
- 项目全量 `black --check` 与 `isort --check-only` 仍有既有格式债务；本次新增 Python 文件已通过针对性检查。
- 项目默认 mypy 配置固定 Python 3.11，与当前 NumPy 的 Python 3.12 stub 语法冲突；本次变更模块已使用实际 Python 3.12 运行时单独检查通过。
