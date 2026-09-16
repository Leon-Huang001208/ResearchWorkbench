# Windows Web Bootstrap 长路径校验修复

## 范围

- 仅修复 Web 一键安装器对固定 DSH 工作树的 Windows 校验；不修改桌面端、依赖锁或厂商凭据。
- 保持后续 Web 迭代的公开 setup、Doctor、安装文档和原生 macOS/Windows 干净安装 CI 门禁。
- 不新增 Python 或 Node 依赖。

## 失败证据与根因

- 原生 Windows bootstrap 在固定提交 checkout 后返回 `dsh_worktree_modified`；安装、CJPY 与 checkout
  已完成。
- 回归测试在编辑实现前证明 `git status` 只收到 `core.symlinks=false`，没有收到 checkout 使用的
  `core.longpaths=true`、`core.autocrlf=false` 与 `core.eol=lf`。
- 根因是 clone/checkout 与 status 分别拼装 Git 选项；长 staging 路径下，两条路径的 Git 语义漂移。
- 首次修复发布后，Windows 已越过工作树校验，但固定 DSH 的 `fs-ext` 在 `pnpm install` 中由
  `node-gyp` 编译时找不到 runner 已安装的 Visual Studio 2022。隔离原生诊断显示：当前过滤环境和只恢复
  `PSModulePath` 均发现 0 个实例；恢复 PowerShell、Program Files、ProgramData 与 Common Program Files
  标准路径组后发现 1 个实例。因此第二个根因是安全环境允许列表遗漏了 Windows 原生工具链发现路径。

## 修复

- `SetupWebInstaller._git_worktree_options()` 成为 clone、checkout 与 status 的单一命令级配置来源。
- 三个操作统一启用长路径并固定换行语义；Windows 额外统一使用 `core.symlinks=false`。
- 校验仍使用 `--untracked-files=no` 并拒绝其他已跟踪修改；不修改机器级 Git 配置。
- Windows Node 构建只额外继承标准系统工具链路径，仍过滤 `CJ_KEY`、模型密钥和其他应用环境变量。

## 验证

- 编辑实现前：目标回归测试按预期失败，实际 status 参数缺少长路径和换行配置；编辑实现后同一测试通过。
- 初次发布后的 Bootstrap Run `35105256163`：macOS 干净安装、启动、Doctor 成功；Windows 已越过
  checkout/status，随后在 `fs-ext` 的 Visual Studio 发现阶段失败。其余 Project Constraints 与 Tabbit
  Runs 成功。
- 隔离诊断 Run `35115008215`：过滤环境与只恢复 `PSModulePath` 均发现 0 个 Visual Studio 实例；
  恢复标准 Windows 工具链发现路径后发现 1 个实例并成功结束。
- 第二轮实现后的 `tests/research_web/test_setup_web.py`：22 passed。
- Ruff、Black、isort 通过；目标源码 `mypy --follow-imports=skip` 通过。常规传递 mypy 仍命中仓库既有
  `core/observability`、MCP Runtime/Registry 的 16 个无关类型错误，本修复未扩大范围。
- 文档同步与项目约束：0 violations；Research Web 架构门禁：52 passed。
- 原生双平台 bootstrap CI 结果在交付完成时补录；CI 完成前不外推 Windows 安装结论。

## 未覆盖边界

- 天软当前仍由厂商 HTTP 401 阻塞；本修复不读取或变更 `CJ_KEY`，也不把依赖安装成功当作数据源可调用。
- 原生双平台 CI 完成前，不宣称 Windows 一键安装已通过。
