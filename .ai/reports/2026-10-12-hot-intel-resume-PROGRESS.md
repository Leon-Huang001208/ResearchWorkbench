# Hot / 研究情报接续记录

宿主 macOS，任务类型功能开发。目标仍为原 Goal 的阶段 0–5，未完成任何门不降级。

## 断点与保全

- 原 worktree：`/Users/leon/.codex/worktrees/hot-events-system/ResearchWorkbench`。
- 原分支：`codex/hot-events-system-20261007`；候选 `fc60414f6c38a0a9e677a8d137c397a0c1895373`。
- 原权威记录：`2026-10-07-hot-events-PROGRESS.md`，完整历史保留；本文件接管后续动作与状态。
- 应用重新绑定被拒绝：原 worktree 属于另一个聊天。未修改原目录或向原聊天发消息。
- 本次 worktree：`/Users/leon/.codex/worktrees/hot-intel-continuation/ResearchWorkbench`。
- 本次分支：`codex/hot-intel-continuation-20261012`。
- 原 5 个已跟踪改动及 3 个新增文件已通过 Git binary patch 恢复，8 文件逐字节一致；原 Git 状态未变化。
- 保全证据：`logs/hot-resume/resume-receipt.json`；补丁 SHA256 `b8103eecebb5d4865420231338f71c5f2e4cb1136860d70422117a74dea3662c`。
- 恢复后使用当前 Mac 主项目已有 `.venv/bin/python` 执行 DOCX unittest：5/5 PASS，未安装依赖。仅验证旧 WIP 的局部行为，不认证完整导出路径。

## 最新主线与融合决策

- GitHub API 核对：PUBLIC；最新 master `8a2d4ba75294b3fbe2aa90aa802dfd25a1296a2b`。
- PR #92 已合并：只读资讯雷达，固定 Golddata GET API，8 栏目；没有本地材料库、worker 或模型执行。
- Hot：Node/TS + PostgreSQL + pg-boss，独立版本材料/事件/频道/简报，受控 FastAPI 桥；现有真实两材料/两简报证据保留。
- 用户明确选择统一入口，并要求命名。采用名称建议“研究情报”：本地热点与事件 + 现有外部资讯栏目。
- 页面共用入口与主题；本地/外部数据始终标明来源，保留独立事件身份与覆盖边界。外部列表不直接写入 Hot 或冒充本地材料证据。
- 原 Hot API/CLI、唯一队列和数据库所有权保留；外部 GET 不创建采集任务/模型调用。
- `#/workbench/hot` 与现有 `#/intel/*` 旧链接继续可解析；新导航归研究情报。
- 实现顺序：保全 WIP → 合入最新 master → 路由/导航融合 → 本地相关回归 → 继续原阶段四及其余验收。
- merge-tree 三方预览提示 26 冲突文件，以 UI 路由、文档与生成物为主；日志 `logs/hot-resume/merge-preview.log`。预览不是实际合并完成。

## 未完成与授权边界

本平台验收仍 NOT_RUN/BLOCKED，整体 NOT_READY。DOCX 正式导出/跟踪/研究交接、真实 DSH、持续采集重验、留出样本、联合恢复、Mac Docker、干净安装与 exact-SHA Mac CI 均未由本次认证。Windows/Linux 为设备交接。无生产部署或合并主线。

旧记录中的累计付费预算不得重置；本次尚未读取权威预算或验证授权，不发付费调用。后续先核对原授权、账本与有效状态，再使用剩余额度。无外部发送。

下一步：合并最新主线并实现统一导航，保留 Hot 的业务合同和外部雷达只读边界。

<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"恢复的DOCX切片复用既有报告生成器，将纯数据函数抽出供原沙箱内嵌及Hot显式导出调用，不新增执行引擎、队列或会话归属。Hot原件与报告会话分别保留，相关文档和新源码映射同步，产品/恢复验收未冒充通过。","diagrams":[]} -->

## 2026-10-12 本地融合实施

- 主线已合入工作区，全部文本冲突解决，最新模型设置、Office编辑、Mac mini部署基座与Hot代码保留。原 worktree 未变，接续补丁仍在本地日志。
- 统一入口“研究情报”：本地 `#/intel/hot` + 外部8栏目，共用栏目导航；旧Hot深链接保留查询参数。外部GET不入Hot库、不创建任务/模型执行。
- RED：新统一路由/导航测试因旧链接无目标失败；GREEN：Hot/Intel 17/17。Research Web JS 385 PASS / 1 SKIPPED / 0 FAIL；治理/策略/Docker静态合同223/223 PASS。
- 用户允许本worktree隔离测试依赖。`.validation-tools` 安装 pytest9.1.1 / pytest-asyncio1.4.0，仅测试工具，不改变产品锁或全局环境。运行依赖复用当前Mac主项目受管解释器，Node用已有24.19.0；Hot依照原package-lock执行npm ci --ignore-scripts，未改版本。
- Hot类型检查与40/40 TS单元PASS。Python Hot/Intel/报告等103 PASS，6子用例PASS。首轮隔离解释器沙箱导入失败后改用既有受管解释器加载隔离pytest，不放宽sandbox。
- 旧定价夹具固定10月9日与严格当日校验冲突；测试的合成价格改用当前日期，增加昨日价格拒绝/不落盘反例，7/7 PASS。生产价表/账本/付费授权未改。
- 文档治理、完整191文件约束、架构清单/API检查、Python索引和API图册检查PASS；01部署图按实际合并源码重新deliver9/9与四视口容纳PASS，Codex查看1440浅色/2048深色最终截图。02/11沿用原分支完全相同字节的历史review，不冒充新产品验收。
- 实际浏览器本地18096预览PASS：单一入口、本地未配置状态、真实外部事件页面、旧链接sources参数保留、规划中栏目及无JS错误。截图和固定边界在 `logs/hot-resume/browser-receipt.json`；预览是内存凭据+离线研究，无Hot模型/研究/DB验收。原框架后台仅写独立预览目录，不计Hot来源采集。
- 内置browser-client因classic-level原生模块加载失败，保留事实；使用已提供的CUA浏览器通道完成浏览验证。首预览fixture不保存临时凭据导致MCP key-race，改为实例内存dict后启动，未读取宿主秘密。
- 首轮所有失败日志保留在 `logs/hot-resume/`；未发远端push/PR/CI、未部署生产、未改变预算。后续仍需完整Hot链和本平台验收。

下一步：完成本次候选本地运行门并保存合并检查点；随后核对原PG资源/模型授权账本，继续DOCX正式导出、跟踪和冻结原文研究交接。当前Goal ACTIVE，hostAcceptance BLOCKED（候选CI/产品验收未执行），aggregateAcceptance NOT_READY。

## 候选本地门收束

- Router保持L4，失败后使用validation_failure重规划，未降级。运行模式/Docker控制/协议/平台能力/API闭包546/546 PASS（250.74s），与Hot/Intel/报告103项为重叠目录的两个闭包，不相加宣称独立覆盖。
- 当前改变的20个Python源码/测试编译PASS。新Hot/融合相对origin/master的完整diff whitespace PASS；相对旧Hot HEAD的merge diff会看到主线已跟踪的Claw原始失败日志行尾空白，保留上游真实日志未修改，并且当前变更范围不包含这些日志的新编辑。
- preview服务通过原TTY session Ctrl-C退出0，独立浏览器tab已关闭；未停生产Web/DSH、未删资料或PG卷。
- 本地检查点可提交；这不是完整Goal、本平台最终验收或合并/发布就绪。尚无候选GitHubCI、干净Hot安装、真实Hot/DSH研究或Docker切换回执。
