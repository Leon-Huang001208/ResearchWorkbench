# 业务报告指令冲突与 FOMC 数值故障修复

宿主为 Mac mini/macOS Native，任务类型为 Web 功能修复；Windows/Linux 产品验收由对应设备交接，未执行不标 PASS。

## 失败与根因

2026-10-20 同版本四用户真实批次：四任务完成但均 incomplete；工具错误9/2/6/9；24下载200、111跨用户拒绝、清理与原会话模型保全通过。本轮读取该批原始失败样本，未复用已消费的临时密钥授权。

真实 Native 历史证明 request/header 与 user/message 都含 report_plan；不是 schema 缺失。服务后续却同时要求手写 numeric_claims、拼装payload与旧写报告函数，四个模型均未采用配方。真实 CPI 上传回归先重现此冲突（1失败1通过），修复后两条路分别通过。

FOMC 六段实际脚本已在原 Mac Native 沙箱离线重现：Path 未定义、列表tuple索引错误、四次数值声明形状拒绝。真实 Summary 缺 cut_bps=50，另写 target_cut_bps=5；冻结负例分别拒绝错键和仅改键后的错值，不修测试报告字节换取通过。

## 改动与边界

仅在实际合法数值业务观测存在时统一初次规范报告与唯一补查指令，使用既有 report_plan；一般资料仍保留原 payload 路径。独立代码计算与取证能力不变，规范报告全部数值、来源、notes、coverage、分析及 missing 仍由原 Host 门检查，不新增来源认证、预算、工具或自动重试。

真正来源/分析/外部真实性缺口仍可使报告 incomplete。指令回归与离线配方成功不证明真实模型会采用，也不证明业务通过；修复部署后按新的一次授权独立复验。

## 验证

证据位于本任务私有 operators/business-claim-loop-20261020/logs，当前先完成失败样本与目标回归；最终集成、评审、CI、部署与真实模型状态另按实际回执记录，未执行不声明通过。无依赖安装、数据库迁移、现有会话/模型设置修改。

## 结构决定

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "只按真实业务观测选择原工具数据参数，不新增HTTP接口或可信请求字段，Host合同与质量检查保持独立", "diagrams": []} -->
<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "指令变更仍在原DSH回合与唯一补查授权中执行，不新增调度、后台生成或模型循环", "diagrams": []} -->
<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "既有script工具与沙箱保持，配方提示不扩大Tabbit、宿主路径或进程权限，也不新建执行引擎", "diagrams": []} -->

## 源分支已执行结果

真实CPI路由红测1失败1通过，修复后2通过；fusion/revision定点46通过（138.17秒），JS及架构/治理133通过；原四组失败公开资料Native配方回放全部通过六格式与原冻结工作簿oracle，模型调用0。FOMC六实际失败脚本原样重现，错误仍拒绝。约束、文档、文件索引、Ruff/Black/isort及service.py Mypy通过；Mypy发现的原合同可空类型加显式dict收窄，非法合同仍不返回report_context。首次约束/README摘要长度检查失败均保留过程，补齐实际模块文档后重验通过。集成全门与真实模型状态仍待执行，不能用源分支定点替代。

## 评审发现与修正

首个候选b6e的Python独立评审发现quote-only兼容P2：原plan必须有数值Summary，纯定性输入不应强制该路线。首次提示与JS唯一补查同时改为只有business_numeric才走plan；纯引文保留观测索引及可用legacy，不编造count或放宽plan/Host检查。新增真实quote-only上传、补查不续授权两路回归；plan分支不再残留手填coverage指令。首候选未发布，修正后重新评审。

评审P2修正后三类实际上传/普通资料路由3通过（13.35秒），近处JS22通过；首轮全部定点46通过作为历史，最终集成候选须重跑，不沿用被拒候选的批准。
