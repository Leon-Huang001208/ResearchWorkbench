# 今日发现完整实现

宿主为 macOS，任务为 Web 功能开发。本轮复用既有 Intel GET、Store/DataHub、唯一 DSH、Automation/APScheduler 与 Host 质量门，不新增依赖、数据库或运行引擎。

## 已实现

- 研究情报默认提供今日发现；仅展示真实来源，失败、陈旧、未知时间和第三方判断缺口可见。
- 新建研究和跟踪先只读核对完整详情，使用独立缓存身份；首页摘要与详情不同不会放宽版本门。冻结后才创建原 DSH 会话，用户再次确认才提交研究。
- 保存跟踪为 disabled，独立开启／暂停；按既有账户容量恢复，只处理本模块本账户批准范围。无新证据跳过模型，同一未知提交不重发，每天最多一次模型尝试。
- Fingpt／Claw 均使用原质量契约；执行完成不等于正式报告接受。跟踪接受核对现有私有质量检查收据、报告版本及哈希。

## 实际验证

- 真实固定公开源：60 条事件；详情预览后会话数为 0；冻结为 snapshot_ready，execution_started=false。来源返回 stale=true 保留显示。DSH 使用协议夹具，真实模型调用为 0。日志：`logs/discovery-live-selection-summary.json`。
- Host／协议／质量范围／原数据存储回归：320 passed，1 个既有弃用警告。日志：`logs/discovery-host-native-regression.log`。
- 来源／交接／跟踪合同最终 60 passed；API 接线 7 passed。日志：`logs/discovery-selection-save-green-20261023.log`、`logs/discovery-selection-routes.log`。
- 完整 Research Web 前端回归：1075 passed、3 skipped；新增详情接线独立复审再跑 34/34。治理闭包 230 passed。本机集成 106 passed、1 skipped。保留各日志中的真实 skip 原因。
- 独立 Python、JavaScript 评审所发现问题已修复并复审通过；增量详情复审绑定文件 SHA-256。
- 真实 Host 隔离浏览器完成 Fingpt／Claw 提交跳转、保存未开启、开启、暂停与刷新恢复；1440px 浅色、390px 浅／深色核查，窄屏 scrollWidth=390，抽屉宽 390、高 844。模型与调度时钟均为 inert fixture，无生产运行。
- 全量 changed-set Router 为 L4/full-delivery；本机完整约束、架构、文档治理、索引及目标格式检查已执行。最终候选、CI 与交付回执将在真实发布后单独绑定。

## 失败与修复证据

- 真实来源同 revision 的 compact／detail 语义不同，原冻结门正确拒绝；新增只读详情确认后跑通，保留原失败日志。未忽略 hash。
- 原测试环境 docx 为外部符号链接，被既有 macOS Seatbelt 正确拒绝。改用已安装的生产 Web 解释器加载真实本地 docx，父测试进程复用既有 pytest，不安装依赖、不改沙箱；原失败与诊断保留。
- 未知跟踪响应、配置恢复、草稿履历、真实质量收据与离榜事件等独评问题均有先红后绿回归。具体合同见 `docs/research-web-discovery.md`。

## 独立边界

本轮没有部署常驻服务、启用生产计划、调用真实模型或修改凭据。真实模型成稿质量、生产定时触发与认证常驻页面为 NOT_RUN；Windows/Linux 产品验收交对应真机。Mac 本机、通用仓库 CI、同候选 macos-14 干净安装以及总体验收分别记录，不以夹具或本机成功代替。
