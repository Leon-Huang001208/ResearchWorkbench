# Research Web 一键本地安装

## 支持范围

首版支持 macOS 与 Windows 的 Web 产品，不安装 Tauri、桌面 sidecar、数据库或桌面安装包。用户需先安装：

- Python 3.12
- Node.js 22.19+（22 系列）或 24.x；Node 23 和 25+ 不在支持范围
- Git
- Windows：Visual Studio 2022 Build Tools 的 “Desktop development with C++” 工作负载；固定 DSH 的
  `fs-ext` 原生模块需要本机编译，安装器不会静默安装或修改系统工具链

Wind、iFinD、Office 等厂商/系统软件是可选能力，缺失不阻止 Web 主体启动。模型密钥、`CJ_KEY`、
Cookie 和账号只在本机设置页录入，不进入代码包、安装清单或日志。

## 公开入口

macOS：

```bash
./setup-web.sh
```

Windows：

```bat
setup-web.cmd
```

跨平台底层入口：

```bash
python scripts/setup_web.py
```

默认流程会检查前置条件、创建项目自有 `.venv`、按哈希锁安装 Web 依赖、校验并安装随包
`cjpy==0.5.2`、构建固定 DSH、启动 3081/8088 并打开浏览器。可用参数：

- `--check-only`：只检查，不写入。
- `--repair`：只修复带本项目所有权标记的 `.venv` 或 DSH 目录；未知目录拒绝覆盖。
- `--no-start`：安装完成但不启动服务。

Node 选择顺序为：调用方显式传入、`RESEARCH_NODE_BINARY`、可执行的 Codex bundled Node、PATH。
安装器会把选中 Node 的目录放在 npm/Corepack/DSH 构建子进程 PATH 首位，避免版本检查使用 Node 24
而原生模块实际由 PATH 中的 Node 25 构建。Node 23 与 25+ 仍关闭失败，不会自动下载替代运行时。

安装完成后可运行：

```bash
./rwb web doctor
./rwb web doctor --json
./rwb web start --no-open
./rwb web status
./rwb web stop
```

Windows 将 `./rwb` 换成 `rwb.cmd`。Doctor 的 JSON 只包含版本、摘要、端口和健康状态，不输出路径、
环境变量值、凭据或用户文件正文。
`rwb web start` 会在创建 3081/8088 子进程前复用 Doctor 的安装检查。若 checkout `.venv` 不受安装器
所有、锁摘要不符、CJPY/Node/DSH 未就绪，命令立即列出稳定 issue code，并提示重新运行上述安装器；
它不会先创建候选 Runtime 再等待健康超时。
安装成功还会从已验证 DSH state 原子刷新 `research-web/runtime/build-lock.json`；Doctor 返回
`dsh.runtime_lock_matches`，锁缺失或与当前 commit/closure/文件数不符时报告
`dsh_runtime_lock_mismatch`，不会把“安装清单有效”误报成 Runtime 可启动。
锁路径逐级拒绝符号链接和 Windows reparse point；POSIX 使用 no-follow 目录描述符完成 0600 原子
替换并拒绝 hardlink，Doctor 以相同边界有界读取。写锁前会把当前用户拥有的产品 data home 收紧为
0700；未知 owner 或 alias 不自动修复。closure 文件数只接受 JSON 整数，不接受浮点等价值。

## 依赖与固定制品

- `.venv` 位于 checkout 根目录，只由安装器管理，不写入全局 Python。
- `requirements/web.in` 是 Web 直接依赖；`requirements/web.lock` 是 Python 3.12、macOS/Windows 通用、
  带哈希的解析结果。用户端只消费锁文件。
- 根项目包以 `--no-deps` 安装，避免把历史 PostgreSQL、LangGraph、量化和桌面依赖引入 Web 环境。
- `vendor/cjpy/0.5.2/` 保存批准的 Apache-2.0 wheel、来源、许可证与闭合哈希清单；禁止回退到
  PyPI 的旧版 CJPY。`vendor/dsh-tabbit/0.3.4/` 的归档、MIT License 与 manifest 同样属于固定供应
  闭包。仓库属性禁止 Git 在 Windows checkout 改写这两个制品目录的字节，确保同一清单摘要可在
  macOS 与 Windows 验证。
- DSH 只从 `Leon-Huang001208/deepseek-harness` 获取提交
  `c919b2a460753859665db3f60143d525fb9140cf`，使用 `pnpm@11.7.0` 和 frozen lockfile 构建。
  Git clone、固定提交 checkout 与后续干净工作树校验都使用同一组命令级配置：
  `core.longpaths=true`、`core.autocrlf=false` 和 `core.eol=lf`，因此 Windows 不依赖机器级 Git
  长路径或换行配置。固定提交包含 Git symlink；Windows 额外统一使用 `core.symlinks=false`，接受 Git
  官方的普通文件表示但仍拒绝其他修改。首次启动会先用固定 DSH 模板
  初始化 `web` Profile，再写入已校验的 Tabbit bundle；
  不能依赖开发机残留的 `profiles/web/package.json`。
  Windows Node 构建只额外继承 PowerShell 模块、Program Files、ProgramData、系统盘与 Common
  Program Files 的标准发现路径，使 `node-gyp`/MSBuild 能定位并运行用户已经安装的 Visual Studio
  工具链；密钥和其他应用环境变量仍不进入子进程。
  安装器固定闭包文件数，首次成功构建后将当前安装目录对应的闭包摘要写入受管标记和安装清单，
  后续 Doctor 按该本机证明检测篡改。CSS Modules 会把绝对构建目录影响到产物摘要，因此不把任意用户目录误声明为
  同一全局摘要。GitHub 不可达、提交/来源/文件数不符，或本机证明后续不匹配时，安装关闭失败，不使用任意本机 DSH。
  DSH 构建子进程使用用户私有数据目录中的 Corepack shim；嵌套构建也固定解析 `pnpm@11.7.0`，不依赖全局 pnpm。

安装清单写入用户私有 `~/.research-workbench/install/manifest.json`，仅记录代码提交、Python/Node
版本、Web 锁摘要、CJPY 版本/摘要、DSH 提交/闭包和诊断状态。安装日志位于仓库 `logs/setup-web.log`。
安装子进程只透传平台基础变量和标准 `HTTP(S)_PROXY` / `ALL_PROXY` / `NO_PROXY` 网络配置；Git 可使用宿主的
SOCKS 代理，Corepack/Node 仅保留其支持的 HTTP/HTTPS 代理。代理值不写入日志或清单。macOS 构建原生 Node
模块时，安装器通过 `xcrun` 发现当前 SDK 的 libc++ 头文件，不写系统路径。`CJ_KEY`、模型密钥及其他应用秘密不会传给安装命令。

## 天软状态

安装成功只证明 `cjpy==0.5.2`、`requests` 与 `urllib3` 可导入。没有 `CJ_KEY` 时，天软必须显示
“依赖已安装但待配置”，`configured=false`、`callable=false`；保存后的 Key 在每次探测和查询时从
系统凭据库动态读取，不要求重启。认证、权限、限流和厂商不可达分别显示，不能把依赖安装成功当作
真实数据成功。

## 后续迭代门禁

任何 Web 功能、Python/Node 依赖、DSH、CJPY、启动或配置流程变更，都必须重新核对本文件、
`requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py` 和 Doctor。仓库级
`.github/workflows/research-web-bootstrap.yml` 对相关 PR 与主分支更新在干净的 GitHub `macos-14`
runner 上运行公开安装入口、构建固定 DSH、启动 3081/8088、检查 Doctor，并验证无凭据天软不会
误报可调用。本机 macOS 验证必须先通过，但不能替代该远端干净环境门。Windows Web 自动验证当前
暂停；`.github/workflows/research-web-windows-verify.yml` 仅保留手动入口，Windows 实机结果由用户
单独提供，未运行时不得标记为通过。该边界不改变桌面/Tauri/sidecar 的独立 Windows 门禁。

维护者更新直接依赖后，用 Python 3.12 重新生成锁：

```bash
uv pip compile requirements/web.in \
  --universal \
  --python-version 3.12 \
  --generate-hashes \
  --no-strip-markers \
  --output-file requirements/web.lock
```

提交前必须从干净 checkout 运行一键安装；不能以开发机已有 `.venv` 或全局模块作为交付证据。
