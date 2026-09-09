# Research Web 脚本沙箱（macOS 实验性）

本模块是 Research Workbench 的独立、默认拒绝脚本边界，不修改 DSH upstream。模型只提供 Python 源码；可信服务提供解释器、脚本 runner、研究根目录及限额。它不是 DSH 自带 `sandbox-local` 的写入限制，也不是容器或虚拟机。

## 启用契约

1. 独立 DSH 实例使用独立 `DSH_HOME`、专用端口和干净启动环境；不要继承模型密钥或数据库环境变量。模型凭据由该实例 Web 表单另行配置。
2. 在 DSH host 根作用域安装单调的 `ctx.tools.guard` 白名单。只启用经过审核的 `research_run_script` 及必要的原生子 Agent/消息工具；不得挂载裸 `fs-local`、shell、文件读写、搜索或其他宿主执行工具。仅仅隐藏工具描述或使用 `restrict` 不是安全边界。
3. 将 `app/research_web/runtime/research-tools.mjs` 作为原生 Cordis 插件注册到所需 agent preset。插件 `inject = ['tools', 'sessions']`，调用 `ctx.tools.register`；无额外 DSH 包导入或 MCP 进程。
4. 插件配置由服务控制，不允许模型参数覆盖：

   ```yaml
   python: python
   runnerPath: /absolute/pinned/build/app/research_web/sandbox.py
   researchRoot: /Users/leon/.research-workbench/research-web
   timeoutSeconds: 15
   maxOutputBytes: 65536
   ```

5. 顶层 DSH session 的 `header.cwd` 必须为 `<researchRoot>/sessions/<UUID>`，必须是规范真实目录。工具不接收工作目录。原生子 Agent 必须沿 `header.parentSession` 链共享同一目录；祖先缺失、循环、超过 16 层或 cwd 不一致均拒绝。恢复冷会话前应先恢复其祖先，否则不会执行。
6. 部署方负责创建会话并将输入及精选研究资源复制到该会话；不允许把宿主目录、符号链接或硬链接作为资源暴露。被允许的运行库和 venv 必须是管理员控制、无凭据的可信依赖；不执行 `.pth`、用户 site 启动文件或项目启动代码。不要把整个项目或用户目录列入白名单。

工具参数仅为 `{"code": "..."}`。返回 `{status, stdout, stderr, exit_code, error}`；状态包括 `completed`、`failed`、`timed_out`、`output_limit`、`cancelled`。请求取消或 supervisor 协议失败会使原生工具报错，不伪装成功。最多 65,536 UTF-8 源码字节；stdout/stderr 合计最多配置字节数，截断的不完整 UTF-8 后缀会被丢弃。

## 内核边界

`sandbox.py` 是只依赖标准库的可信 supervisor，不导入 `core.settings`，不读取 `.env` 或数据库配置。它先验证配置的解释器，再以 `/usr/bin/sandbox-exec` 启动隔离的 `-I -S -B` Python。非 macOS 或无 Seatbelt 时拒绝执行，不退回裸 shell。

| 资源 | 脚本权限 |
| --- | --- |
| 当前会话 `inputs/`、`resources/` | 只读 |
| 当前会话 `outputs/`、`tmp/` | 可读写 |
| 研究根目录 `index.json`、其他会话、宿主项目/配置/凭据 | 不可读数据，不可写 |
| 系统运行库、显式配置的 Python 实际 base prefix 和 venv site-packages | 只读 |
| 运行库链接的 Homebrew dylib | `otool -L` 得到的真实单文件只读，不开放整个 Homebrew |
| IPv4/IPv6/Unix 网络 | `deny network*` |
| fork、非指定 Python exec、Mach lookup/register、POSIX IPC、进程查询、signal | 拒绝 |

Seatbelt 使用 `allow default` 加 `deny file-read-data` 与明确运行库/会话 allowlist，`deny file-write*` 只对 outputs/tmp 和 `/dev/null` 例外。系统读取范围为 `/System/Library`、`/usr/lib`、`/usr/bin`、`/usr/share`、`/bin`；随机源设备仅具体文件。Python 启动需要 `(literal "/")`，这不等同于允许读取整个根目录树。文件元数据仍可见，不能承诺隐藏宿主路径存在性。

`deny process-exec` 的例外仅为显式 Python 真实可执行文件及其 framework launcher；同一解释器再次 exec 仍继承父 Seatbelt。禁止 fork、任意 shell 和 Mach/IPC 路径，避免把请求转交无沙箱进程。没有任何模型可控的环境变量或可执行文件参数。

子进程环境精确为 `PATH`、`LANG`、`LC_ALL`、`TMPDIR`、`MPLCONFIGDIR`、`XDG_CACHE_HOME`、`__CF_USER_TEXT_ENCODING`。tmp/cache/Matplotlib 配置均指向当前会话 tmp；不继承 API key、数据库地址、HOME、PYTHONPATH、BASH_ENV、DYLD 变量。标准库 MIME 表提前初始化，避免文档库读取宿主 `/etc` 配置。

## 资源与错误处理

资源导入：运行器把当前会话 `resources/` 的可信绝对路径加入 Python 导入路径。
脚本直接 `from research_helpers import read_pdf, write_deliverables`；不要添加相对
`sys.path`（其解析依赖被拒绝的 `getcwd()`）。本修复不增加 Seatbelt 权限。

- 墙钟限额可配置为 `(0, 60]` 秒；源码传输、执行与输出收集共用非阻塞截止时间。
- CPU 硬限额为墙钟向上取整加一秒；打开文件上限 64；单文件大小硬限额 16 MiB。
- 超时、取消和输出超限杀死独立进程组；清理等待最多一秒。无法确认内核清理时返回失败，绝不声称终止成功。
- supervisor 协议有独立输出上限和超时；原生工具取消先发送 SIGTERM，再有界处理异常清理。
- CLI 日志写 `<researchRoot>/logs/sandbox.log`，只记录固定事件、状态及异常类型；不记录脚本、stdout、输入或凭据。嵌入调用使用标准 logging，可接入现有日志 sink。该独立模块故意不导入会读取应用设置的日志入口。

仍未提供总磁盘配额、总内存/RSS 限制、容器级 CPU/线程配额。Seatbelt 是宿主内核安全边界，不抵御内核漏洞或恶意本机管理员；macOS 内核不可中断进程也可能无法立即清理。不适合不受信任多租户或高风险任意代码托管。需要这些保障时应使用另行审核的 VM/容器执行服务，不能放宽当前规则。未验证 Linux/Windows 支持。

## 已执行验证

在原生 macOS、上面的已存在 Python 3.12 venv 上，通过不调用模型的本地测试验证：

- inputs/resources 读取、outputs/tmp 写入；Word、Excel、PNG 实际生成，docx/pdfplumber/openpyxl/matplotlib 导入。
- 自建无敏感宿主 canary、其他会话 canary、`index.json`、系统 Data 卷别名、符号链接和硬链接越界拒绝。
- inputs/resources 与会话根写入拒绝；真实本机监听端口连接拒绝；fork、创建新 session 的 `posix_spawn` 和 `/bin/echo` exec 拒绝。
- 环境白名单、超时、输出限额、不可信 cwd、符号链接目录、非法配置和非 macOS 默认拒绝。
- 原生工具注册、可信子 Agent workspace 继承、祖先 cwd 不一致拒绝、Unicode 输出、取消。
- 脚本关闭 stdout/stderr 后取消：修复前回归证实延迟写入，修复后 50ms 轮询仍响应取消，PID 已回收且等待原定执行时长后无延迟文件。

测试只创建临时 canary，不读取真实秘密。测试故意隔离仓库全局 `conftest.py`，避免加载应用数据库设置：

```sh
python -m pytest --confcutdir=tests/research_web tests/research_web/test_sandbox.py -q
node --check app/research_web/runtime/research-tools.mjs
```

这些测试证明列出的本机行为，不代替全局 guard 集成审核或真实 DSH 模型工具调用验收。默认先用禁工具聊天确认专用实例和凭据；只有白名单及当前构建边界验证完成后，才能开启此工具。
