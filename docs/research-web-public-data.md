# 研究公开数据原生工具

`runtime/public-data.mjs` 注册 13 个品牌无关的 `datahub_*` 业务 Tool。上游请求、分页、解析与快照统一在 FastAPI 的 `datahub/` 模块。产品改名不要求重命名 `datahub_*` 协议；完整目录、接口与数据口径见 [DataHub](research-web-datahub.md)。

## 不变边界

- trustedDirectory沿实际原生会话父系验证产品目录，模型不传session/path/url/header。
- 每次先请求DSH原生审批；只接受allowed-once。拒绝、取消、审批不可用或未通过目录校验时零HTTP。
- 后台子Agent原生approval=never，由父Agent先经批准准备资料，再共享只读CSV/JSON。
- 不改DSH版本、模型、执行额度、全局工具白名单或脚本Seatbelt权限，不加MCP/守护进程。

## 新契约

业务契约使用 `capability`、能力限定 `parameters`、可选目录 `source`、`allow_fallback` 和 `refresh`；不接受任意 URL、头、凭据、模块或路径。目前 `datahub_get_fund_data` 与 `datahub_search_news` 分别映射到已适配的东方财富基金与财联社 Provider。
NAV成对日期在最多十年内且非未来，按实际PageSize/PageIndex/TotalCount分页；旧limit仍仅最近一页、最多100条，不能冒称完整历史。
补充来源每项单独审批；持仓year可选。基准文字不等于序列，当前资料不等于历史时点，累计净值不等于总回报。

审批后插件读取固定`.control/datahub.json`，检查0600/属主/非symlink/非hardlink，取可信回环地址与独立随机产品凭据。
内部URL路径由代码固定，拒绝重定向；凭据不进入模型、脚本环境、日志或Web。
调用ID由实际原生session header.id和exec.callId组成，产品sid只由可信目录UUID得到；DataHub持久校验调用ID与查询指纹。
原生abort/桥接失败发认证cancel，BFF也在会话取消和关闭时停止取数；无法确认远端取消只记固定失败事件，不伪装成功。

返回字符串字段dataset_id/source/status/manifest_json/files_json/sample_json；最多三行样本。
旧rows_json整份数据返回已移除，模型使用research_run_script读取files_json的inputs/datasets只读相对路径。
原始响应仅私有留档，输入资料不混普通附件、报告产物或交付检查。

## 验证

`DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web_public_data.test.mjs`

覆盖私有认证回环路径、审批拒绝零HTTP、参数/身份拒绝、原生取消、凭据文件权限/链接、响应大小和实际DSH schema转换器。
上游结构/分页/缓存/快照/hash/API回归在`tests/research_web/test_datahub.py`及`test_api.py`。
2026-09-02早期旧单页真实验收是历史证据；新版完整范围取数和补充来源探针另见父任务来源核对报告，真实模型闭环不可用离线fixture代替。
