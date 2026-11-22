# 脚本、数值声明与业务证据修复

保全补查另复现旧会话缺新模块的 Native ModuleNotFoundError。SDK 现从 Host 包的四个固定文件只读加载，旧 resources 保持原字节；两个目录只给 literal，不给 subtree 或额外写入。PDF session root 由原 Host 校验根注入，保持输出及 cwd 行为。独立 Python/执行边界评审无 P1/P2，新旧会话 Native 生成/修订和完整沙箱目标29通过/1条件跳过；旧64候选的三个CI通过仅保留为历史，不沿用为新SDK候选证据。

主线前进至 PR143 后，在本任务集成中保留其真实正文读取及逐版本质量绑定。交汇评审发现 P1：Host 网页落盘被再次登记成无日期上传别名，可丢失 web scope/截止日；新增真实 Host 落盘端到端用例先红，来源分类修复后通过。分类依据会话 web_evidence 的 id/path/file_id/Store 映射，不按文件名前缀；统一覆盖服务清单、上下文、观测、评分及业务索引/快照，保留真实日期及所有旧文件。跨会话同路径和损坏登记拒绝也已回归。

旧候选636的 API 首轮900秒超时保留，随后完整202覆盖通过；主线刷新后436的四分片202也通过，但该候选仍因上述 P1 不批准。两次检查均只代表各自 SHA，不能替代新修复候选验证；新候选仍待完整验收、CI、合并、部署及新授权真实模型批次。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"互斥报告数据参数复用原DSH脚本准入及Host检查，无新服务或HTTP端点，严格质量判据保留","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"原会话outputs内暂存六格式并保留旧版本与失败恢复副本，不迁移会话或改变下载校验链","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"数据配方只在原研究回合执行，无新增调度节点、模型循环、补查次数或日程权限","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"原research_run_script保留Native沙箱、槽位、超时及输出预算，数据参数无浏览器或外部执行能力","diagrams":[]} -->

宿主：24GB Mac mini/macOS；功能修复，验收范围为本机 Native、通用仓库检查与 macOS Bootstrap。Windows/Linux 原生验收 NOT_RUN。

原批次四任务均执行完成、24 下载 HTTP200，但全部质量 incomplete；NIST 控制表混入 business observation ID。没有把下载成功当作质量通过。

本轮在唯一 DSH research_run_script 内增加互斥 report_plan 数据参数，Host 私有冻结绑定不由模型指定。原超时、准入、槽位、代码与输出预算不变。Summary 派生值须从实际摘录原值按有界步骤独立计算，Calc 保留96位过程；独立算术一致不证明公式语义或外部真实性。完整父文件来源、notes/coverage/claims 确定性组装；分析、建议和真实 missing 继续进入原质量门。NIST Controls 原文及真实父来源固定，实施状态 not_assessed。

quality.py 仅修复同期间两条已核验声明相互干扰：先移除所有已通过原验证的完整原句，再移除期间。数值、期间、单位、原句、父来源、额外分析及真实缺口的判据不变。

六格式先暂存，归档后最后发布 JSON。回滚先撤下新 JSON、恢复 sidecars 后最后恢复旧 JSON；双重失败保留恢复副本且 canonical 缺失。

已执行：失败 CPI 声明及七类拒绝回归、原 Native 沙箱配方执行/修订、NIST 来源与建议可见性、晚期写入失败和双重恢复失败。focused 161 passed；revision 29 passed；独立评审相关102 passed，P1/P2=0。四组原失败公开字节在原 Native 沙箱回放均 PASS：独立冻结 Summary 数值、严格来源单元格、NIST 控制表及六格式；模型调用0，完整业务分析和并发验收 NOT_RUN。

证据：本机私有 operators/business-evidence-loop-20261019/logs 和 offline-plan.json。最终候选检查、三 CI、合并及部署待完成，不能将旧候选证据复用为本轮通过。真实四用户模型批次须另获本轮临时凭据及槽位授权；此前一次批次授权已消耗。保留现有会话和模型配置，不读取密钥、不放宽质量门。
