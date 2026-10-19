# FinGPT 正文取证、来源登记与报告版本绑定

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"沿原DSH工具、Host私有桥和会话inputs/outputs扩展两项内部操作及有限工具进程；没有新增部署服务、研究循环或聊天正文库，现有工具与资料连线仍适用，API与模块清单已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"沿原DSH工具、Host私有桥和会话inputs/outputs扩展两项内部操作及有限工具进程；没有新增部署服务、研究循环或聊天正文库，现有工具与资料连线仍适用，API与模块清单已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"沿原DSH工具、Host私有桥和会话inputs/outputs扩展两项内部操作及有限工具进程；没有新增部署服务、研究循环或聊天正文库，现有工具与资料连线仍适用，API与模块清单已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"沿原DSH工具、Host私有桥和会话inputs/outputs扩展两项内部操作及有限工具进程；没有新增部署服务、研究循环或聊天正文库，现有工具与资料连线仍适用，API与模块清单已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"沿原DSH工具、Host私有桥和会话inputs/outputs扩展两项内部操作及有限工具进程；没有新增部署服务、研究循环或聊天正文库，现有工具与资料连线仍适用，API与模块清单已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"沿原DSH工具、Host私有桥和会话inputs/outputs扩展两项内部操作及有限工具进程；没有新增部署服务、研究循环或聊天正文库，现有工具与资料连线仍适用，API与模块清单已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"沿原DSH工具、Host私有桥和会话inputs/outputs扩展两项内部操作及有限工具进程；没有新增部署服务、研究循环或聊天正文库，现有工具与资料连线仍适用，API与模块清单已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"沿原DSH工具、Host私有桥和会话inputs/outputs扩展两项内部操作及有限工具进程；没有新增部署服务、研究循环或聊天正文库，现有工具与资料连线仍适用，API与模块清单已同步。","diagrams":[]} -->

- 宿主/任务：macOS，功能修复；本机 Native 与同候选 macOS CI 为交付门，Windows/Linux 产品验收交接保持 NOT_RUN。
- 目标：保留 DSH、数据、模型与质量硬门；修复后通过受管 PR 合并，再在研究空闲门内部署并同题 Flash 复测。
- 基线：2f2ce7a85d72e358d0a2d5b0b3d22f4413890917；原失败会话 546ceb5b-6661-4174-939d-46d6ebd1f5dc 保留。

## 复现与修复

1. 原生 web_search 的 Markdown Sources 不能被 JSON-only 解析器登记。新增真实形状回归先红：1 failed / 24 passed（既有 report_revision 原生沙箱修复已在主线，复用而不重写）。新增解析只保留原始标题/URL和摘要状态。
2. research_read_source 在私有原生回调内列举/读取准确来源，可信原生快照同步有界搜索身份，避免 Host 持久事件滞后。模型不得传URL、正文、会话或认证；Host 保全实际 inputs 字节/哈希，质量检查重读证据。公共HTTPS地址固定DNS、逐跳验证TLS；有限HTTP子进程的总超时与取消均kill/reap，先取消的call_id阻止晚启动，tenant私有key保持。
3. 同回合报告检查回执新增真实规范JSON内容哈希，保存经Host验证的版本锚点与具体检查ID。当前版本不冒充历史；精确版本记录优先，旧fallback哈希不匹配时incomplete，不能继承其他版本passed。旁路JSON不成为规范报告。

## 已完成证据

- 原版本绑定缺少content hash的回归先红：1 failed；修复后的正文/取消/版本定点22 PASS。
- 原生质量/source工具JS定点13 PASS；公共来源读取烟测实际取得国家统计局2025与2024 GDP正文，含1401879/1348066，未调用模型。
- 独立Python/JavaScript工作区初审指出的总超时、取消、版本错绑及tenant回调问题均按证据修正；最终SHA终审仍待完成。
- 日志：logs/fingpt-evidence-version-fix-20261019/。未更改requirements/web.in、web.lock、setup_web.py、DSH pin、研究硬预算或research_quality.py。

## 待验边界

本机检查点：源代码提交11c2b541aa03bd0eefd5e92921e0fd09b6ef94a5；源码8模块mypy、11文件Ruff/Black/isort、架构/API清单/文档完整性均通过。服务/本机集成454 PASS与1个Windows条件skip，研究/账号兼容279 PASS，Node24.19回归828 PASS与2个固定源码opt-in skip，定点33 PASS，完整API/协议283 PASS（1025.48秒）。使用已有依赖环境构建的wheel关键模块字节核验及包内独立进程NBS正文烟测已执行；此项不冒充干净安装，最终打包及干净安装由精确候选Mac CI认证。

Mac干净安装CI、最终SHA独立评审、合并部署、数据配置保留及同题真实Flash复测待后续回执认证。当前不声明研究通过或服务已更新；取证/质量/交付分别留证，不能以模型自评或文件存在代替通过。
