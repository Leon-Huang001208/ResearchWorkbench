# DSH Web 实施记录

本轮以 Web → FastAPI → DSH 原生 RPC / 双 WebSocket 为唯一研究链路。
不加载旧数据库、研究运行器、知识处理和桌面生命周期。

## 实施顺序

1. 原生协议、归属索引、历史与 SSE；FinGPT 页面集成。
2. 专属运行实例、模型授权、严格文件访问约束与真实聊天验收。
3. 资料上传与生成文件；真实工具和产物验收。
4. 原生 Skill、Claw 子 Agent、异常与浏览器回归。

## 边界

- 用户现有 3080 只做协议验证，不修改配置、重启或复制其凭据。
- 新入口 `app.research_web.main:app`，仅回环地址运行。
- 产品索引只存会话归属、文件标识、幂等收据；历史正文来自 DSH。
- 连接中断不重发问题；未知受理结果要求先查看历史。
- 缺少安全工具运行环境时禁止调用工具，不把 cwd 当沙箱。
- 实际模型旅程尚未验收；测试通过不代表真实研究完成。

## 开发启动

在本隔离工作树根目录运行两个终端。使用已安装项目依赖的 Python 环境；本机验证解释器为 `/Users/leon/Desktop/Projects/AlphaFoundry-runtime-agnostic-core/.venv/bin/python`。

```bash
python -m app.research_web.launch_runtime --source /Users/leon/Developer/deepseek-harness --data /Users/leon/.alphafoundry/research-web --source-mode --research-tools
python -m uvicorn app.research_web.main:app --host 127.0.0.1 --port 8088
```

入口：`http://127.0.0.1:8088/#/settings`。模型密钥只在此填写，不从 3080 或仓库环境文件复制。
DSH 源码固定 `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`；CLI 版本为 `0.1.1-rc.2`，`host.describe` 当前协议实现报告 `0.0.1`。启动器记录实际本地源码/构建闭包哈希。
现有 `lib` 构建不完整，所以本轮使用固定源码和已安装 tsx 启动；这不是经过发布验证的独立构建包。
不带 `--research-tools` 可启动禁工具聊天模式；无法完成沙箱启动检查时不要开放脚本。

## 数据与模块

- `client.py`：允许列表 RPC、关联 ID 检查、双下行通道和历史分页。HTTP 超时只限制受理，不限制任务时长。
- `service.py`：会话归属、事件归一、状态恢复、幂等提交、原生子Agent取消、审批与问题响应。
- `store.py`：原子本地 JSON 索引（单 Web worker），不保存模型正文；文件使用不跟随符号链接的目录描述符打开。
- `main.py`：回环 Web API、安全来源边界、上传与隔离预览；无旧业务启动钩子。
- `ui/`：正式五页与原生模块，详见 [UI 文档](research-web-ui.md)。
- `runtime/`：专属 DSH composition、工具白名单与每轮执行上限。
- `skills/`：资料解读、公司研究、行业研究、基金评价四类原生 SKILL.md、脚本与模板；禁止扫描用户其他全局 Skill。
- `resources/`：实际 PDF 页码抽取、Office/HTML/Markdown 文件生成与重开检查。

数据根默认 `~/.alphafoundry/research-web`（可通过 `AF_RESEARCH_DATA` 指定）。其下：

```text
index.json                   # 归属、默认模型和幂等受理收据
runtime/home/                # 专属DSH历史与凭据
runtime/work/                # 干净启动目录，无.env
runtime/*-lock.json           # 本地源码/构建锁
sessions/<uuid>/inputs/      # 上传资料，只读给研究脚本
sessions/<uuid>/resources/   # 审核过的辅助脚本和模板，只读
sessions/<uuid>/outputs/     # 真正生成的文件
```

不得使用多个 Uvicorn worker 并发写同一索引。研究正文只读 DSH 日志；浏览器断线不取消任务也不自动重提。

## 验证命令

```bash
DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness python -m pytest tests/research_web --confcutdir=tests/research_web -q
node --test tests/javascript/research_web*.test.mjs
python -m ruff check app/research_web tests/research_web
python -m black app/research_web tests/research_web --check
python -m isort app/research_web tests/research_web --check-only
python -m mypy app/research_web --exclude '/skills/' --follow-imports=skip
python scripts/check_task_completion.py
python scripts/check_doc_sync.py
```

Skills 的同名独立脚本要逐文件执行 mypy，避免模块重名。真实模型验收单独记录，不以 MockTransport/TestClient 代替。
`DSH_SOURCE_ROOT` 只用于测试已存在的原生 JSON Schema 转换器；未设置时该项会跳过，不能据此宣称协议验证完整。

## 原生协议与产品细节

- Session 提交只等待受理；`events.mux` 与 `events.host` 同时连接。完整内容从原生日志分页读取，事件重连清除投影基线但不重新提交。
- DSH 重启后先用 `session.models` 恢复记录中的 preset，再查询 `skill.list`；不会创建替代会话或重复发送。
- 子 Agent 活动来自 `subagent.list/history` 的父子归属接口；每个子 Agent 展示最近100条消息的投影，`history_truncated` 明确说明更早内容未加载，1秒缓存减少重复读取。
- 父回合结束但子 Agent 仍运行时，详情和历史保持运行状态；停止调用原生父会话取消及直接子 Agent interrupt，不把受理当作已停止。
- 模型配置、创建及发送共用单进程锁；配置完成才发布产品默认模型，运行中的原生会话不被热切换。
- 图片附件转换为原生 image content（单张8MiB、合计16MiB），DSH负责媒体校验和模型兼容性；其他文件作为只读inputs路径交给研究工具。上传30MiB上限不表示模型能接收等大图片。
- 本地索引不保存聊天正文；Office检查在生成助手中执行，尚未加入独立的“用户要求格式→最终产物完整性”产品验收器，不能仅凭回合completed判定报告交付全部满足。

## 当前未完成的外部验收

- 专属模型未提供密钥时只能验证原生协议、历史和失败路径，不能完成真实问答/子Agent研究。
- 公共检索由 DSH 原生 `web_search` 走明确的 DeepSeek 搜索提供方；不开放任意网页 fetch。
- 财联社专用接入、额外金融 HTTP/MCP 尚未配置，不能声称已可用；禁止自动安装第三方插件或继承其他产品凭据。
- 长任务真实停止/审批拒绝/模型中途故障、最终用户报告质量与完整旅程仍需有凭据后验收。
- 当前文本/图片多模态都尚未通过真实模型验收。批准流程已接入原生消息，但没有通过实际工具触发的审批旅程。
- 早期固定Python启动探针 PID 38291 留在macOS内核 `UE` 状态；SIGKILL后未确认回收，临时目录 `/private/tmp/af-dsh-sandbox-probe.frLuyJ` 保留。它不是模型脚本；旧实验profile快照不完整，不能保证其权限/句柄状态。当前有效runner的全部取消测试已正常回收。
- 未涉及桌面/Windows、市场首页/主题/自选、旧系统数据删除。
