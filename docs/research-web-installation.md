# Research Web 一键本地安装

## 支持范围

首版支持 macOS 与 Windows 的 Web 产品，不安装 Tauri、桌面 sidecar、数据库或桌面安装包。用户只需先安装：

- Python 3.12
- Node.js 22.19+（22 系列）或 24.x；Node 23 和 25+ 不在支持范围
- Git

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

## 依赖与固定制品

- `.venv` 位于 checkout 根目录，只由安装器管理，不写入全局 Python。
- `requirements/web.in` 是 Web 直接依赖；`requirements/web.lock` 是 Python 3.12、macOS/Windows 通用、
  带哈希的解析结果。用户端只消费锁文件。
- 根项目包以 `--no-deps` 安装，避免把历史 PostgreSQL、LangGraph、量化和桌面依赖引入 Web 环境。
- `vendor/cjpy/0.5.2/` 保存批准的 Apache-2.0 wheel、来源、许可证与闭合哈希清单；禁止回退到
  PyPI 的旧版 CJPY。
- DSH 只从 `Leon-Huang001208/deepseek-harness` 获取提交
  `c919b2a460753859665db3f60143d525fb9140cf`，使用 `pnpm@11.7.0` 和 frozen lockfile 构建。
  安装器固定闭包文件数，首次成功构建后将当前安装目录对应的闭包摘要写入受管标记和安装清单，
  后续 Doctor 按该本机证明检测篡改。CSS Modules 会把绝对构建目录影响到产物摘要，因此不把任意用户目录误声明为
  同一全局摘要。GitHub 不可达、提交/来源/文件数不符，或本机证明后续不匹配时，安装关闭失败，不使用任意本机 DSH。

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
`.github/workflows/research-web-bootstrap.yml` 对每个 PR 与主分支更新在干净的 `macos-14` 和
`windows-2022` runner 上运行公开安装入口、构建固定 DSH、启动 3081/8088、检查 Doctor，并验证
无凭据天软不会误报可调用。该门禁属于 Web 交付，不触发桌面/Tauri/sidecar 验收。

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
