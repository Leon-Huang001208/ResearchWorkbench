# Markdown 代码块关闭围栏结构复核

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅修正既有 Markdown 渲染函数的代码块关闭行判定并增加回归；沿用原浏览器渲染与 HTML 转义边界，不新增 UI 服务、依赖、研究执行器或部署节点。","diagrams":[]} -->

任务：ResearchWorkbench Issue #270；仅更新原 PR #274。

原候选 `7cdc3e3a443b543fdc7d72c4335b18d5e7e4197a` 的独立会话评审已批准；本次五项治理文档补充已获本人专项授权；新候选仍须重新验证及独立评审，结论以各自精确版本回执为准。原 Project Constraints 未通过，不能据本记录宣称 CI 或业务验收通过。

保持现有 UI 架构；README 产品入口不变，关联模块文档分别记录展示、研究框架及 ETF 周报边界。原修复不扩展 Markdown 子集，不改变链接安全处理和代码转义。只交付 PR，不合并、不部署。
