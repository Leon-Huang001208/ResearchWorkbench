# 脚本、数值声明与业务证据修复

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
