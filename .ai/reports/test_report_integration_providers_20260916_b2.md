# 现有 DataHub Provider 闭环测试报告

## 范围

任务 `integration-providers-20260916-b2` 覆盖天软、AKShare、用户 MySQL、财联社和东方财富基金的
探测、业务查询、快照与 Runtime 路径。只修改 Web DataHub、共享 Python 依赖、测试和 Web 文档；
不修改桌面/Tauri/sidecar。

## 实现

- AKShare 探针由慢速全量证券目录改为固定新浪交易日历 URL 的可取消异步 HTTP 流，禁用代理/
  重定向、限制 16 KiB；3 秒连接与 8 秒读超时受 10 秒总墙钟限制，取消后立即释放查询共享容量。
- `pyproject.toml` 在 `tinysoft` 可选依赖中精确声明 `cjpy==0.5.2`，并用
  `requirements/tinysoft.lock` 锁定已批准 wheel 的 SHA-256；保留并实际安装验证
  `PyMySQL>=1.2.0`。基础安装不依赖不可公开解析的厂商制品。
- 天软按 CJPY 异常类型和安全 HTTP 状态映射认证、权限、限流、网络与 schema 错误；MySQL 按
  驱动错误号映射认证、权限、数据库、忙、网络/TLS错误。天软拒绝成功响应中的当前 Token 反射；
  日志只记录错误类型和安全错误码。
- 新增真实探针契约、秘密不泄漏和 PyMySQL 驱动错误映射回归测试。

## 依赖证据

- Python 3.12 临时 venv 使用厂商本机 wheel 安装 `cjpy 0.5.2`，并从公开索引安装
  `PyMySQL 1.2.0`，两者共同导入成功。
- 当前项目 Anaconda 环境安装并导入 `PyMySQL 1.2.0`；已有 `cjpy 0.5.2` 可导入。
- 公开 Python 索引的 `cjpy` 最高版本为 0.3.6，不能满足精确的 `cjpy==0.5.2`。全新环境须先安装
  普通项目依赖，再从批准的本地 wheelhouse 使用 `--no-index --no-deps --require-hashes` 安装；锁文件
  SHA-256 `d8c6820a…5bd94` 已与本机厂商 wheel 复核一致，本批没有把厂商 wheel 提交到仓库。

## 真实公共来源证据

2026-09-16 在 macOS 上使用真实上游只读请求，未使用 fixture：

| 来源 | 探针 | 耗时 | 业务查询 | 结果 | Runtime 工具 |
| --- | --- | ---: | --- | --- | --- |
| AKShare | healthy | 1206 ms | `market_bars`，600000.SH，2025-09-01..05 | complete，5 行 | `datahub_get_market_bars`，5 行 |
| 财联社 | healthy | 243 ms | `search_news`，最新 2 条 | snapshot，2 行 | `datahub_search_news`，2 行 |
| 东方财富基金 | healthy | 341 ms | `fund_data/nav`，000001，最近 3 条 | snapshot，3 行 | `datahub_get_fund_data`，3 行 |

三次 Python DataHub 查询和三次 Node Runtime 工具调用均生成 `rows.json`、`rows.csv`、
`manifest.json`，并返回独立 dataset ID。临时验证目录不进入仓库。

## 已执行验证

- 目标测试先红后绿：新增 6 个测试初次全部失败，实现后全部通过。
- Provider 目标测试：46 passed。
- DataHub/连接中心/协调器综合回归：153 passed。
- Research Web 等价全量覆盖：排除多进程工作流文件的主套件 899 passed、4 skipped；单独运行完整
  `test_report_workflows.py` 为 55 passed，合计覆盖 958 项。此前单进程长跑末尾的 5 个多进程超时
  已聚焦复跑为 5 passed；拆分运行避免长跑后的 spawn 资源时序干扰。
- 当前宿主注入 `ALL_PROXY/all_proxy` SOCKS5 代理，而项目未声明可选 `socksio`。未增加无关依赖；
  Research Web 全量验证使用 `env -u ALL_PROXY -u all_proxy` 隔离宿主代理。隔离前首个 setup error
  可稳定复现，隔离后同一测试为 1 passed。
- JavaScript 公共数据、连接中心和本机集成 UI：39 passed、1 skipped。
- Ruff、Black 23.11、Black 26.5、isort、mypy（`--follow-imports=skip`）、`git diff --check`、
  文档同步和 Research Web 架构检查均通过。
- 安全复审确认厂商依赖漂移/混合索引、Token 字典键反射、AKShare 慢速分块三项风险均已修复；
  代码质量复审结论为 APPROVED。
- 真实 Provider/DataHub 冒烟：3 个探针 healthy；3 个真实查询完成并发布快照。
- 真实 Runtime 冒烟：3 个常驻 `datahub_*` 工具经受控回环接口调用成功。

## 未完成与诚实边界

- 天软：代码、依赖和错误映射已就绪，但没有通过产品凭据库获得用户授权 Token，也没有触发厂商
  会话；真实探针、真实查询、快照和 Runtime 调用未验收。
- MySQL：驱动、只读/TLS/授权契约和错误映射已就绪，但没有用户提供的可达只读测试库配置；真实
  连接、schema 查询、业务查询、快照和 Runtime 调用未验收。
- 临时 Runtime 冒烟启动了完整 ResearchService，因框架调度器的既有启动行为同时执行了框架采集；
  冒烟完成后服务已关闭。该行为不是本批代码改动，后续应优先使用隔离的 DataHub-only Host fixture。
- Windows 只接受后续原生 CI；本批没有宣称 Windows 桌面实测，也没有触发桌面交付门禁。
