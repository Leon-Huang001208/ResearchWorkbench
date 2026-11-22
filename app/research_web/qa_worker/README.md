# AlphaDesk 问答编排

`agent.mjs` 和 `prompts.mjs` 迁自 AlphaDesk 提交 `1c946b9a0930d3070da7263ffcffe5e8831077c3` 的 `server/agent.mjs`、`server/prompts.mjs`。已获得将问答源码纳入公开 RWB 的授权。保留三档工具循环、计划、复核、写作提示、引用和进度事件。RWB 改用 Host 已授权的模型和工具，按证据 ID 分配本轮引用编号。Agent 的工作笔记是研究过程输出，报告产物状态由 Host 提供。上游项目的账户、积分、原工具供应商、技能服务器和文件模拟事件均未引入。

[固定版本编排](https://github.com/yuxudong-morefun/AlphaDesk/blob/1c946b9a0930d3070da7263ffcffe5e8831077c3/server/agent.mjs) · [固定版本提示](https://github.com/yuxudong-morefun/AlphaDesk/blob/1c946b9a0930d3070da7263ffcffe5e8831077c3/server/prompts.mjs)

上游 Git blob 分别为 `9b8c28ae9c8ae6c95805b839c17e1bddf117c640` 和 `507a7479faa0c286d8d798f39ad0fbb7e182c1ba`。

本地提示按本轮用户范围和 Host 冻结要求安排计划、复核与写作。综合投研问题保留默认分析维度、章节和篇幅；限定 RSS 摘要核对只处理要求的来源字段与摘要事实，不自动增加全文、行情、第二来源或采集精度调查。`source_ids` 由报告 SDK 原样呈现已绑定的来源元数据、RSS 摘要及核对范围。`missing` 只记录未满足本轮冻结要求的定性资料缺口，不重复范围说明或复制日期、URL、数字及算式；无本轮缺口时为空数组。若用户确实要求而尚未取得全文或独立来源，仍保留实际缺口。三档循环、默认 fallback、工具授权及 Host 的事实和财务数值校验不变。

Host 可信交接为 `registered_feed` 时，同一个 `write_research_report` 工具只声明来源元数据计划：`title`、`sections`、`missing`，每节为 `id`、`heading`、`source_ids`、`requirement_ids` 与空 `evidence_ids`。正文由已绑定来源自动呈现；聊天分析不进入正式摘要清单。传入 `analysis`、数值底稿或其他未声明字段会明确返回 `qa_report_metadata_plan_required` 及修正说明。普通财务和其他来源继续使用完整报告计划，事实与数值绑定校验保持。
该计划的 `source_ids` 仅枚举可信交接中本轮已选公告的准确 `file:` ID，各节来源并集必须覆盖这些公告。控制快照的 `dataset:` ID 不作为公告来源，误用会返回 `qa_report_metadata_source_invalid`；遗漏公告会返回 `qa_report_metadata_sources_incomplete` 并列出待补 ID。工具不会自动补入来源或据此伪报完整。

## Host 私有协议

Host 每轮启动一个 `worker.mjs` 子进程。所有帧为 UTF-8 JSON 单行，单帧上限 1 MiB，子进程输出累计上限 16 MiB。Host 负责凭据、账号及轮次绑定、运行预算、进程停止和结果持久化。

- Host 首帧为 `{type:"start",mode,question,history?,framework?,tools}`。`framework` 结构为 `{name,text}`，用于传入经 Host 绑定的研究资料。工具使用 OpenAI function schema。
- 子进程发出递增编号的 `{type:"call",id,method,params}`。模型参数为 `{messages,tools?,maxTokens}`。工具参数为 `{name,arguments,toolCallId}`。Host 应按当前轮次和授权独立核验工具名及参数。
- Host 以相同 `id` 回送 `{type:"result",id,result}` 或 `{type:"error",id,error:{code}}`。模型结果为 `{content,toolCalls,reasoningContent?}`，模型输出增量可在最终结果前发送 `{type:"delta",id,content}`。原始推理字段只用于同轮模型工具对话续接。工具结果为 `{data,sources?,warnings?,artifact?}`，引用至少带 `evidence_id` 与 `title`，可附 `url`、`provider`、`asof`。
- 子进程输出 `{type:"event",event,data}`，结束时输出 `{type:"done"}` 或 `{type:"failed",code}`。完成表示编排结束，报告质量和是否绑定以 Host 的独立结果为准。`write_research_report` 仅在 Host 声明时开放，深度和 Agent 模式只在最终写作阶段使用。只有该工具返回的 `artifact` 可以生成 `report_artifact` 事件。
- `read_frozen_dataset` 与 `read_frozen_discovery` 接受可选行 `offset`，默认从零开始；每页返回同一快照的 `offset`、`next_offset` 和 `total`，按 `next_offset` 续读至 `null`。完整 `data` JSON 每页不超过 23,000 个 UTF-16 单元，包含快照身份、时点与限制。报告计划失败时，仅将 sandbox 中明确的 `ValueError: research_*` 标识作为工具错误码返回；未知错误保留 `qa_report_plan_failed`，不传出 stderr、堆栈或路径。

本地离线协议验证使用 `node --test tests/javascript/research_web_qa_worker.test.mjs`。
