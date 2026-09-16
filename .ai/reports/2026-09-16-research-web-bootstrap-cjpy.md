# Research Web 一键环境与 CJPY 0.5.2 实施记录

## 范围

- Web-only；不修改 Tauri、desktop、sidecar 或桌面安装包。
- macOS/Windows 公开一键入口与 checkout 专属 `.venv`。
- Python 3.12 跨平台哈希锁、随包 CJPY 0.5.2、固定 DSH 构建与安全安装清单。
- `rwb web doctor [--json]`、天软依赖/错误状态与动态凭据读取。
- 后续迭代持续维护安装环境和流程的仓库规则及原生双平台 CI。

## 实现事实

- `scripts/setup_web.py` 支持 `--check-only`、`--repair`、`--no-start`；未知 `.venv`/DSH 目录、
  符号链接及重解析点关闭失败。
- `requirements/web.lock` 由 Python 3.12 universal 解析生成并带完整哈希；根项目包以 `--no-deps`
  安装，历史数据库/量化/桌面依赖不进入 Web 环境。
- `vendor/cjpy/0.5.2/` 只接受批准 wheel
  `d8c6820a718ae5f79061b54815473dd3ecd3be73cd808634fbac5bc1c385bd94` 及闭合清单。
- DSH 固定仓库 `Leon-Huang001208/deepseek-harness`、提交
  `c919b2a460753859665db3f60143d525fb9140cf`、`pnpm@11.7.0`、frozen lockfile 和 11084 个闭包文件。
  CSS Modules 会把绝对构建目录参与客户端摘要，因此首次构建原子写入本机闭包证明，后续 Doctor 按该证明检测篡改；
  不再把某一绝对路径的摘要误当作跨用户全局常量。
- Node 支持范围收紧为 22.19.x+ 或 24.x；本机 Node 25.9.0 构建 DSH `fs-ext` 失败，安装器和 Runtime 都关闭失败。
- Git 保留宿主 SOCKS 代理；Corepack/Node 过滤不支持的代理协议。macOS 通过 `xcrun`
  安全发现 SDK libc++ 头文件，供 DSH 原生模块构建使用。
- 安装子进程只接收允许列表环境；安装清单和 Doctor 采用允许列表输出，不记录密钥、Cookie、
  环境变量值、本机路径外内容或用户文件正文。
- 项目 `AGENTS.md` 与 `.github/workflows/research-web-bootstrap.yml` 要求以后每次 PR/主分支更新在
  干净 `macos-14`、`windows-2022` 上执行公开 setup、固定 DSH 构建、3081/8088 启动、Doctor 和
  无凭据天软不可调用断言。

## 已执行验证（功能分支交付前）

- Web 锁在隔离 worktree 的 `.venv` 完整安装，锁闭包阶段 `pip check` 返回
  `No broken requirements found`。
- 根包以无依赖模式安装，随包 `cjpy==0.5.2` 安装并真实导入；同时导入
  `requests==2.34.2`、`urllib3==2.8.0`。
- 完整 Research Web Python 回归：987 passed、4 skipped；格式化后的改动相关回归：157 passed。
- 完整 Research Web JavaScript 回归：279 passed、1 skipped（280 tests）。
- Ruff、Black、isort、文档同步、项目约束、JSON/YAML/Bash 语法和 `git diff --check` 全部通过。
- 修改的 7 个 Python 源文件在隔离导入模式下通过 mypy；严格传递检查仍命中仓库既有的 24 个类型错误，
  本批没有扩大修复范围。
- 项目约束检查：0 violations。
- 安装器首次重复运行正确移除旧根包元数据，在 Web 锁阶段完成依赖一致性检查，再重装当前根包；
  证明中断后重试不会误把历史全量 metadata 当作 Web 锁缺失。
- 当前 Mac 已用项目 `.venv` 和 Node 24.19.0 完成真实 DSH 构建；最新 Doctor 为 `ok=true`，报告锁、
  CJPY、DSH 及 3081/8088 健康。Web 子进程会过滤无效/SOCKS 代理，避免 `httpx` 因未安装可选
  `socksio` 而启动失败。
- 已保存的天软配置在每次探测时从系统凭据库动态读取；本次真实探测达到厂商后返回
  `vendor_auth_failed` (HTTP 401)。因此已证明 `configured=true`、`dependency_ready=true`、
  `restart_required=false`。交付前再次真实探测，246 ms 后仍返回 `vendor_auth_failed`；统一状态为
  `probe_state=unavailable`、`runtime_callable=false`、`bucket=user_action`、`responsibility=user`，因此不宣称
  `health=healthy` 或真实可调用。

## 尚未完成或不可外推

- 新增的原生 macOS/Windows bootstrap workflow 尚未在远端运行；合并前不得宣称 Windows 已通过。
- 天软当前阻塞于厂商认证，未进入无回退业务查询、不可变快照和 Runtime Tool 验收。需用户在本机设置页更换或确认厂商有效
  `CJ_KEY`；无需重启服务。本记录未读取、输出或迁移该密钥。
