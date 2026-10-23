# 华安 ETF 周报 Excel 先行：取数前置检查

宿主 macOS，任务类型 Web 功能开发；任务 `etf-excel-first-20261023`。
用户已明确暂停 Client API，改用现有 Wind Excel 跑真实生产与交付，以后再校准切源。
工作区由受管入口从远端 master 建立，AlphaFoundry 全程只读。

## 实测与进展

- 本机已有 Wind、Excel、Word；原项目运行环境可导入 xlwings/openpyxl。
- 用户已完成 Wind 安全验证。早期 WSD 查询超时及原生公式自动化失败均保留；后续原生指数公式、
  WSD 历史行情与 TDAYS 交易日查询实际返回。成功查询使用客户端持有的工作簿，完成后正常关闭。
- 本机 `lsappinfo` 返回多行 `pid = ...`，xlwings 按首个等号解析而失败；原客户端把枚举失败当作
  无实例并启动新应用。候选修复仅规范化该私有模块的 PID 响应，未知失败明确拒绝，不修改厂商安装。
- Mac 溢出范围中的空单元格实际返回空字符串，原读取器把 6 条历史记录读成 1000 行；候选修复
  同时裁剪空字符串/None 并保留零值。初版离线测试 123 项通过；后续修改需重新验证。
- 已通过 Wind 原生界面导出下一周经济日历至任务 logs 目录；完整日期范围、筛选范围与来源证据
  仍须检查，不能仅凭文件下载完成认证覆盖。
- 原底稿 `周报数据.xlsx` 使用 `TODAY()`、减七天、固定除五；其外链指向 Windows WindFunc.xla。
  原 `全球经济日历.xlsx` 是静态单元格，不能仅重算工作簿就认证已覆盖目标下一周。
- 既有新生产 collector 依赖 Client API 及 API/Excel 校准，不是 Excel 主来源路径。
  旧比较输入主要是汇总值，不能替代 Host 独立重算所需的原始端点、逐日成交和交易日期。

## 当前状态

已实现显式 `wind_excel` 来源模式、同版本原始快照、EDB 数值导出与经济日历输入；
沿用原 Workflow/DSH/Host canonical 正文与定稿硬门。API 原分支保留用于以后校准切换。
离线 provider、API/Excel 完整定稿合成回归及原 API/Workflow 回归通过；最近补查的历史时间边界
29 项通过。真实取数覆盖不等于真实成稿：完整模型、Word 逐页验收、常驻部署均未执行。
用户最新明确保持定时任务关闭；即使手工成功，本次也不启用。
未修改任何旧 AlphaFoundry 文件，未关闭已有 Excel 工作簿，也未使用缓存冒充本期新取数。
改动仍未提交或发布，规范评审发现的经济日历范围证明与时间合同缺口正在修复。
早期独立实例 PID 91804 的关闭回执曾失败，后续只读进程复查已不再存在；没有强杀或关闭用户实例。
API 权益仍未判断，保持推迟。不得继续把身份验证写为当前阻断。

## 最新真实诊断

- 用户已保存 EDB 数值文件。OOXML 原始物理行与维度 A1 不一致，读取器重置维度后核对
  四个原始 ID、单位及历史数据；派生 s1 换算列排除。该文件是手工原生数值导出，不能认证自动刷新。
- 原生经济日历周窗口为周日到周六；下一周周日已实际观察两页均无事件，并保留原生文字证据。
  原生窗口和全筛选证据仍须与文件哈希绑定，缺证不把声明当成覆盖。
- 新建独立 Excel 进程心跳通过但 WSD/TDAYS 一直 Fetching。同样公式在既有 Wind-loaded
  Excel 的任务自有新工作簿中成功；国庆范围返回 9/28–30、10/8–9、10/12–16。
  详见 `logs/etf-excel/calendar-main-existing-control.json`。全部十三市场日历仍未认证。
- 新生产连接仅在已有 Excel 中新建任务工作簿；明确 -50 创建拒绝且前后工作簿清单不变时
  才尝试下一实例。未知结果阻断并保留 worker poison，不自动创建新应用或关闭已有应用。
- 用户确认市场截止时间保留周五15:30，实际取数结束立即冻结并展示真实冻结时间；历史期重查
  必须标为事后复核，不能冒充当时快照。该新时间合同及反例回归实施中。

## 恢复后执行

继续核验十三市场日历 ID、假期和已结束交易日语义，再完成真实数据门；
保留同源身份、实际交易日、实际日期、原始响应/工作簿哈希与质量门。只在本期 Run 副本处理旧公式。
API 等价校准仅用于未来切源，不作为当前 Excel 来源的准入条件。
数据门通过后进行一次完整真实研究、Host 核验、原模板交付与下载检查，失败保留证据，不自动重发未知模型请求。
本次定时保持关闭；三周稳定性仍需实际周期观察。

## 本地实现验收与结构决策

规范评审原生范围、历史截止及定时三项已闭环；未知工作簿创建结果保持 sticky，关闭失败传到
共享 Wind poison，后续 call_id 不重发。Python 独评无 P1/P2；UI 独评修复 API 历史定稿误算
Excel 验收后通过。实际回归：完整周报组合114项、Provider最终40项、实例23项、原适配器组合
137项、相关JS14项。Ruff/Black/isort/mypy按实际目标通过；最终完整改动集治理与CI仍待执行。
这些是离线实现证据，不替代真实供应商、Word、下载或部署验收。

<!-- architecture-review {"group":"report-workflows","structure":"changed","reason":"原报告工作流增加Excel主来源合同及原生双页范围证据，Host市场截止和实际冻结分离，原DSH与canonical投影保持，09/10图同步来源分支","diagrams":["09-report-workflow-sequence","10-excel-report-dataflow"]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"Excel周报分支位于原私有DataHub与Wind执行槽内部，04数据图的Host与供应商边界保持；具体来源合同语义在报告09/10图更新，无新服务或共享来源","diagrams":["04-data-file-flow"]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"沿既有周报详情卡显示来源版本及历史验收并禁用Excel日程，事件路由和页面拓扑保持，09/10业务图已同步来源语义","diagrams":["09-report-workflow-sequence","10-excel-report-dataflow"]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只在既有Checks Python步骤加入Excel Provider与实例回归，不新增job、runner、依赖或平台dispatch，原验证路由及图拓扑保持","diagrams":[]} -->
