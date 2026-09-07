# 研究公开数据原生工具

`runtime/public-data.mjs` 声明 13 个品牌无关的 `datahub_*` 业务 Tool，但 Research Runtime 只注册启动时 `enabledTools` 中至少有一个可调用来源的工具。上游请求、分页、解析与快照统一在 FastAPI 的 `datahub/` 模块。产品改名不要求重命名 `datahub_*` 协议；完整目录、接口与数据口径见 [DataHub](research-web-datahub.md)。

## 不变边界

- trustedDirectory 沿实际原生会话父系验证产品目录，模型不传 session/path/url/header。
- DataHub 只读查询不调用逐次审批服务；非法参数、伪造会话、非本地地址、不安全控制文件或未通过目录校验时零 HTTP。其他工具和高风险操作的审批机制不变。
- 后台子 Agent 不直接重复调用 DataHub，由父 Agent 自动查询一次并共享只读 CSV/JSON 数据集快照。
- 不改DSH版本、模型、执行额度、全局工具白名单或脚本Seatbelt权限，不加MCP/守护进程。

## 新契约

业务契约使用 `capability`、能力限定 `parameters`、可选目录 `source`、`allow_fallback` 和 `refresh`；不接受任意 URL、头、凭据、模块或路径。可调用来源由离线能力目录决定，例如已配置的东方财富基金和财联社 Provider；不存在可调用来源的工具不会暴露给模型。
`launch_runtime.py` 在每次 Research Runtime 启动时重新生成 `enabledTools`；来源配置变化后必须重启 Runtime 才会生效。目录生成失败时拒绝启动，避免误注册无来源工具。
NAV成对日期在最多十年内且非未来，按实际PageSize/PageIndex/TotalCount分页；旧limit仍仅最近一页、最多100条，不能冒称完整历史。
补充来源不再逐项审批，但仍须已配置、启用且满足凭据要求；启用后的付费查询也自动执行。持仓year可选。基准文字不等于序列，当前资料不等于历史时点，累计净值不等于总回报。

插件启动和调用时读取固定 `.control/datahub.json`，检查 0600/属主/非 symlink/非 hardlink，取可信回环地址与独立随机产品凭据。
内部URL路径由代码固定，拒绝重定向；凭据不进入模型、脚本环境、日志或Web。
调用ID由实际原生session header.id和exec.callId组成，产品sid只由可信目录UUID得到；DataHub持久校验调用ID与查询指纹。
原生abort/桥接失败发认证cancel，BFF也在会话取消和关闭时停止取数；无法确认远端取消只记固定失败事件，不伪装成功。

返回字符串字段dataset_id/source/status/manifest_json/files_json/sample_json；最多三行样本。
旧rows_json整份数据返回已移除，模型使用research_run_script读取files_json的inputs/datasets只读相对路径。
原始响应仅私有留档，输入资料不混普通附件、报告产物或交付检查。

## 验证

`DSH_SOURCE_ROOT=/path/to/dsh-source node --test tests/javascript/research_web_public_data.test.mjs`

覆盖私有认证回环路径、查询不调用审批服务、参数/身份拒绝零 HTTP、动态工具注册、原生取消、凭据文件权限/链接、响应大小和实际 DSH schema 转换器。
上游结构/分页/缓存/快照/hash/API回归在`tests/research_web/test_datahub.py`及`test_api.py`。
2026-09-02早期旧单页真实验收是历史证据；新版完整范围取数和补充来源探针另见父任务来源核对报告，真实模型闭环不可用离线fixture代替。
