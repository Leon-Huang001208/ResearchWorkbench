# Claw 原生关联与异常退出恢复 Goal

1. 目标：普通 Skill/Workflow 与报告 Workflow 及时记录原生关联，异常退出后接回同一任务，不重复研究。
2. 基线：远端 master 与主 checkout 同为 `4a5e7523d7407525d108757727c64f10783203f4`；独立分支 `codex/claw-native-recovery-20261009`。
3. 平台：macOS 功能开发；当前任务只作本地候选，不发布、不运行付费模型或用户任务。
4. 边界：优先仅改 automation/service.py、最近测试和必需模块文档/任务证据；API/schema、依赖锁、DSH 与用户数据只读。
5. 任务0：核验运行关联、提交/恢复语义、现有测试与 Store 原子写；基线测试依赖缺失如实记录。
6. 任务1：先构建创建→监控中的最小 RED，不能手工预填关联 ID 冒充生产路径。
7. 任务2：原生 ID 已知即持久化；提交未知、持久化失败或归属未知失败关闭，不自动重发；显式停止保持原语义。
8. 任务3：两类创建/中断/恢复、缺关联、错误与持久化失败回归；临时私有根和独立进程验证异常退出。
9. 任务4：完整 changed set 规划、本地门/文档/回执/审查；CI/真实模型/他平台保留 NOT_RUN。
10. 当前：独立 pytest 环境已获授权并建立，初始三类 RED 均复现，当前关联/恢复修复已落盘。

## 实施与证据

- 初始六套测试 29 PASS；新增持久化、未知提交、缺 ID、报告事实源与归属回归均先 RED 再 GREEN。
- macOS 私有临时根、真实 Web 子进程 SIGKILL 和独立受控 loopback 执行器：旧基线三类 FAIL，新实现三类 PASS；不认证真实 DSH/model。
- 报告在恢复时优先监控报告 Run；晚到 Claw session ID 也及时落盘，必须锁定 workflow/version。
- 只读评审发现首次保存失败时的陈旧引用取消边界，已加两条 RED并修复：先验证事实源与本次新建归属，仅在已验证新建运行的初始保存失败时取消。
- 当前继续：受控进程重跑、文档同步与本地门；质量工具临时安装申请仍待明确同意。

## 断点

- 当前 128 Python / 110 Node PASS，三类进程恢复 PASS，文档/索引/架构/Project Constraints PASS。
- 最终只读审查 Approve；代码保存于本分支，不修改前轮 FinGPT 候选或主 checkout。
- 唯一当前安装批准待决项：ruff/black/isort/mypy 临时环境用途说明已发，未获答复，不重复安装或请求。
- 授权后使用 `/private/tmp/rwb-claw-test-env.Z0DP8D`，不改主 .venv/锁；对 changed Python 源码做质量检查和同工具基线对比，任何新修改重跑对应测试/进程和更新 sourceSHA256。
- 完成后保存正式 plan/receipt、真实 NOT_RUN CI/安装/模型/他平台项，最后 Harness 和 Goal 结项。

- 续轮已完成正式 plan/receipt（38文件）与 validator valid=true/BLOCKED，五本地门 PASS；完整证据已归档。质量工具安装批准仍待决，已做一次无变化环境审计；同一阻塞连续两轮，未重复询问/安装。若后续第三轮仍无授权且没有独立工作，应按真实阈值标记 blocked。

- 第三轮审计：四项质量工具仍缺失，授权仍待决；源与进程回执 SHA 一致。无独立结项工作剩余，Goal 转 blocked，保留候选与全部证据，等待明确授权和恢复。

## 授权后恢复

- 用户明确授权四项质量工具在原临时环境安装；主环境、锁和全局配置保持。
- 同版本旧基线 Ruff/Black/isort/mypy PASS；新增代码修正格式/导入及1个无效noqa后四检查 PASS。
- 三文件非导入 AST 与导入集合机械一致，原12测试函数 AST 未改；只读评审确认未引入语义或范围变化。
- 128测试与三类进程恢复复验进行中；完成后更新 sourceSHA/完整changed set/回执，最后Harness和Goal结项。

## 最终本地候选完成

- 授权后128 Python测试、三类真实自建子进程SIGKILL/恢复复验通过，进程回执绑定新source SHA；原12测试AST及格式化前非导入AST/导入集合一致。
- Ruff/Black/isort三文件、mypy当前service.py聚焦检查PASS，旧基线同工具也PASS；正式计划保持L4，五个本地门闭环。
- 本地功能与验收完成，无剩余本地权限阻塞；CI、干净安装、真实模型、他平台NOT_RUN，aggregate/merge/release仍未就绪。

## Harness 结项纠正

- 最后 Harness enforce 返回 `invalid harness event stream`，实际硬门未通过；之前将 Goal 标为完成过早，已恢复同一完整目标。
- 质量授权阻塞已解除；当前核查共享 Git common Harness 账本，不删除、改写或补造历史事件。本地功能证据有效，最终结项仍待 Harness。
- 根因已定位到其他任务事件前133个NUL；原账本与修复预览保存在私有临时目录，预览只改等长JSON前导空白，46805条事件可解析。共享账本尚未修改；只请求一次明确授权，等待后继续最终硬门。
- 范围纠正：诊断期间新增第二处133 NUL损坏，第46809行。原单点授权提案已取代为两处合计266字节；最新备份/预览46855条可解析，尚未应用。写入源未知；后续若新增损坏不自动修复，保留共享Harness阻塞。

## 自动续轮的验收审计

- 上轮有实质进展：定位共享账本损坏、备份并生成可审阅修复预览、更新真实BLOCKED回执。修复授权尚未收到，自动续跑不视作授权。
- 本轮源码/进程回执SHA一致，原12测试AST不变，主checkout受跟踪diff为空；审计发现旧进程证据没有崩溃前已有文件的字节保留证明。
- 已强化独立受控backend，在kill前真实写入并登记中间文件；恢复后对同一路径读取字节和SHA，六份实际before/after快照归档。正常三类PASS；主动破坏临时文件的三类负对照均预期FAIL。
- 旧基线三类仍缺关联FAIL，最新RED/GREEN回执均绑定sourceSHA/probeSHA；探针完成状态竞态已按只读评审修正，复验与最终Approve完成。service.py和产品测试未改。
- 完整changed set增至55，更新正式计划/回执和受影响检查；共享Harness修复仍待授权，没有重复请求或应用修复。最终Goal保持未完成。
- 本轮最终检查：55文件五个策略本地门全部PASS（架构82、完整Node110、0 skip），四QA工具PASS；receipt validator valid=true/result=BLOCKED，非merge/release-ready。Harness只读复核仍返回invalid harness event stream（exit1）。这是同一共享账本授权阻塞的连续第二个Goal回合，仍未达到blocked状态阈值；本轮已完成产物证据缺口修复，无其他不依赖授权的必需工作剩余。

## 第三次阻塞审计

- 上轮为实质进展：补齐崩溃前文件字节保留与破坏负对照、关闭探针竞态、更新55文件计划及本地门。没有将自动续跑当成授权。
- 本轮Harness只读复核仍exit1/invalid harness event stream；修复授权尚未到达。当前service/probe SHA与进程回执一致，三类实际before/after文件SHA一致，无候选漂移。
- 同一共享账本权限阻塞已连续三个Goal回合；无不依赖授权的必需工作剩余，已满足blocked条件。登记Goal为blocked并等待明确授权或账本外部状态修复，不重复请求、安装、测试或诊断。

## 用户授权后的恢复

- 用户明确授权两处共266字节的最小账本修复；本轮不扩大范围，不重新请求授权。
- 经原行SHA/offset/inode检查、0600原始备份与文件/目录fsync后完成两次定位写；原始字节持久备份在.git/leon-engineering/harness-repair-backups/claw-20261009-NLDXb3，未截断/rename账本。
- 独立复核：差异恰好266，完整事件JSON及所有其他既有字节不变；官方全流47,167条严格schema PASS、后续append合法、未发现新增损坏；原生Harness硬门PASS。
- 新增修复回执/日志后完整changed set=57，保持原L4与所有策略门；正在完成受影响本地门与最后回执审计。产品源码/探针/测试未改，不重复与账本修复无关的产品回归；发布、CI、真实模型、其他平台仍NOT_RUN。
- 57文件五本地门复验全部PASS：文档治理、Python索引、Project Constraints、架构82、完整Node110（0 skip）。独立账本核验PASS：恰好266字节差异、其余原字节不变、原备份SHA与权限匹配、全流严格schema与后续append有效。Harness原生硬门PASS，当前本地候选目标完成；总回执仍BLOCKED/非merge-ready，保留所有真实NOT_RUN与损坏来源未知风险。
