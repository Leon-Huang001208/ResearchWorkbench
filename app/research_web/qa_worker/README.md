# AlphaDesk 问答编排

`agent.mjs` 和 `prompts.mjs` 迁自 AlphaDesk 提交 `1c946b9a0930d3070da7263ffcffe5e8831077c3` 的 `server/agent.mjs`、`server/prompts.mjs`。已获得将问答源码纳入公开 RWB 的授权。保留三档工具循环、计划、复核、写作提示、引用和进度事件。RWB 改用 Host 已授权的模型和工具，按证据 ID 分配本轮引用编号。Agent 的工作笔记是研究过程输出，报告产物状态由 Host 提供。上游项目的账户、积分、原工具供应商、技能服务器和文件模拟事件均未引入。

[固定版本编排](https://github.com/yuxudong-morefun/AlphaDesk/blob/1c946b9a0930d3070da7263ffcffe5e8831077c3/server/agent.mjs) · [固定版本提示](https://github.com/yuxudong-morefun/AlphaDesk/blob/1c946b9a0930d3070da7263ffcffe5e8831077c3/server/prompts.mjs)

上游 Git blob 分别为 `9b8c28ae9c8ae6c95805b839c17e1bddf117c640` 和 `507a7479faa0c286d8d798f39ad0fbb7e182c1ba`。

## Host 私有协议

Host 每轮启动一个 `worker.mjs` 子进程。所有帧为 UTF-8 JSON 单行，单帧上限 1 MiB，子进程输出累计上限 16 MiB。Host 负责凭据、账号及轮次绑定、运行预算、进程停止和结果持久化。

- Host 首帧为 `{type:"start",mode,question,history?,framework?,tools}`。`framework` 结构为 `{name,text}`，用于传入经 Host 绑定的研究资料。工具使用 OpenAI function schema。
- 子进程发出递增编号的 `{type:"call",id,method,params}`。模型参数为 `{messages,tools?,maxTokens}`。工具参数为 `{name,arguments,toolCallId}`。Host 应按当前轮次和授权独立核验工具名及参数。
- Host 以相同 `id` 回送 `{type:"result",id,result}` 或 `{type:"error",id,error:{code}}`。模型结果为 `{content,toolCalls,reasoningContent?}`，模型输出增量可在最终结果前发送 `{type:"delta",id,content}`。原始推理字段只用于同轮模型工具对话续接。工具结果为 `{data,sources?,warnings?,artifact?}`，引用至少带 `evidence_id` 与 `title`，可附 `url`、`provider`、`asof`。
- 子进程输出 `{type:"event",event,data}`，结束时输出 `{type:"done"}` 或 `{type:"failed",code}`。完成表示编排结束，报告质量和是否绑定以 Host 的独立结果为准。`write_research_report` 仅在 Host 声明时开放，深度和 Agent 模式只在最终写作阶段使用。只有该工具返回的 `artifact` 可以生成 `report_artifact` 事件。

本地离线协议验证使用 `node --test tests/javascript/research_web_qa_worker.test.mjs`。
