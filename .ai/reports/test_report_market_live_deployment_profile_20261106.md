# 市场综合总览封闭部署操作员准备

日期：2026-11-06。宿主：macOS／Mac mini 开发职责；类型：功能开发与已授权常驻部署准备。
本报告只认证本子任务实现和静态检查，不认证部署成功；实际测试、评审、CI、现场切换与浏览器验收由根任务聚合。

## 固定身份与范围

- 产品检查点：`a2ee934f026d9f174d948a2f748213d0d5021f5b`。
- 新前版：`5ffecb5219d46a5d3e4148a4ddb630f23a09ab3b`，现场身份由根任务只读核实。
- 新封闭入口：`apply-market-live`／`reviewed-market-overview-live-v1`。
- 原 EVENT 的全部既有常量及 review_assets 组合祖先分支经 AST 与 HEAD 比较保持不变。
- 实读锁文件 SHA-256：`7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102`；evidence：`193f4fcc7e27ab1fd9fd87c4d30a0ca200476fe74c6cc4c6c7dad6bb8ce63988`。

## 实现与保护

复用原 version4 三锁、BirthFence、业务索引／全账号 @events 原件保全和恢复。
新 closed family 仅扩展到市场 live 身份，复用日程关闭／冻结原件、Native 严格列表、Host／后台／Workflow／market inflight 空闲门。
目标配置持久 false，双 health 检查实际 MCP 严格 false 与配置／进程出生身份稳定；旧配置原样回滚。
review_assets 同时验证固定前版→产品→最终工具目标祖先关系和两份 diff 的路径并集、blob、文件模式。
仅 MODULE、TEST、docs、.ai/reports 允许产品检查点后的变化；额外 app/scripts/tests/README/outputs 均拒绝。
不修改 controller、evidence、依赖、账号、数据、模型、历史；不启用采集或 MCP，不进入 TRIAL。

## 验证记录

- PASS：共享环境 --check --json，healthy=true；无依赖安装。
- PASS：实际 Git merge-base --is-ancestor 5ffecb5219d46a5d3e4148a4ddb630f23a09ab3b a2ee934f026d9f174d948a2f748213d0d5021f5b，exit=0。
- PASS：两 Python 文件 ast.parse、旧 EVENT 固定常量及祖先分支 AST 比较。
- PASS：black --check、ruff check、isort --check-only，仅本子任务两个 Python 文件。
- PASS：git diff --check。
- 首次 ruff 发现参数化改动后的 unused fixture system 变量，已改为 _system，随后检查通过。
- NOT_RUN：pytest，按根任务要求由唯一最终批次统一运行，未建立临时 pytest 根。
- NOT_RUN：独评、最终 exact-SHA CI／Mac 干净安装、实际常驻切换、认证页面验收、资源收尾；不冒充完成。
- NOT_RUN：Windows／Linux 原生，交由对应设备。

## 测试设计与静态规模估计

原 ASSET_PROFILES 加入新 mode：覆盖真实 Git 并集／回退／模式、全账号索引、前进失败／回滚／恢复、独立 release clone 和配置保护。
13 个 EVENT 实际运行／MCP／恢复 test 函数参数化至两个 mode；旧 EVENT 专属祖先链测试仍只验证旧身份。
另新增新 profile 固定身份、10 项真实 Git 拒绝案例和操作员／文档允许变化正例。
按 AST 顶层参数装饰器静态估算，本文件原 2829 个 case → 2984 个 case（+155），35 个函数 case 数变化；此数字不是 pytest collect 或执行回执。

## 子任务文件 SHA-256

- `research_workbench_entrypoint/resident/model_provider_upgrade.py`: `a85571a93143e25f3b7085b46284a220bd25b683afc8afb8a3830212681d4a0a`
- `tests/research_web/test_model_provider_upgrade.py`: `1d238fcfc0c96295ba4773fd94c7b23728b2b9f2cf0c8c78159fdcdd320359be`
- `docs/research-web-gateway-upgrade.md`: `566cbc7ffb0ac5162af2150c3ff9f3fe985a37bd4c2aa47ab5f018c411c21bc6`
