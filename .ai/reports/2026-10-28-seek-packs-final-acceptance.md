# 研究组合包与原件方法：第二批验收记录

日期：2026-10-28。宿主：macOS Mac mini；任务：Web 功能开发。
任务：`seek-packs-20261027-7bda5752`；基线：`1317968ea7e5e7227adbe9451882b381307438c2`。
当前产品候选：`e411f3aaa7a311a7f59e16cd59d0cf9023e6beab`。
状态：源码、独立审查与 14 个 Router 本地门已通过；最终 CI、同候选 Mac 安装及发布尚未完成，平台回执保持 BLOCKED／NOT_READY。

## 交付范围与使用位置

- 原研究场景抽屉、FinGPT／Claw 和能力中心接入九包确定性内核及三个原件方法：公司资料核验、新闻事实与条件传导、调研材料准备。原八场景与 18 个比较证据门保留。
- 公司、行业／主题按规范身份选择本人已取得原件，可跨会话只读预览、明确冻结、准备原有草稿，再由用户发送；浏览不启动模型。
- 原件绑定来源、权限、时点、内容 hash 与传输完整性私有证明。Host 重验当前权限和原件，Native 使用固定资源，完成后 Host 独立读回；旧版本、缺失和撤权不会静默改取新材料。
- 新闻／调研方法消费 Host 实际执行的 C2 去重制品，保留未知角色、地域、公开时刻与上游覆盖缺口。公司百分比变化由 Host 独立重建正基数策略，SDK 不能删掉策略绕过。
- `rwb_query_latest_cls_news` 沿原 DataHub／CLS／snapshot 链，只提供有界最新快照和正文子串匹配；保留原新闻工具完整参数，不注册供应商别名。三个固定问题预置进入原准备／冻结／发送链。

数据映射当前主要覆盖已核验日线和网页版本；其他财务、持仓、估值、预期输入仍有库内代码和来源合同待补。九个内核不等于九个组合包已完成全部生产验收。140 项／284 参数对照保留 pending、受管 MCP 和后续阶段，不能以卡片、提示词或 static binding 计为功能完成。

## 本轮独立发现及修复

1. 捕获提前 EOF 与发布失败孤儿正文被误认完整／普通附件：加入真实 HTTP framing、Host 私有证明和所有文件别名权限检查；缺坏证明拒绝，不给旧数据补假证明。
2. 方法准备晚期失败留下冻结原件：明确准备事务和只属本次的回滚，提交结果未知保留 unknown，不重试。
3. 预置问题清空旧题后被浏览器 required 拦截：共用有效性谓词，旧场景必填与冲突拒绝仍在；独立真实浏览器复核通过。
4. 工具／Skill 数量和新闭合模式的旧测试欠账：精确保留旧集合、18 个 gate 与 no-spawn，补新增项断言，不使用宽泛数量下限。
5. 两秒互斥测试把真实 2.689 秒资源冻结计入等待：准备屏障完整调用原快照函数，随后保留原两秒 Native 屏障及互斥断言；没有改变产品锁、资源或超时。
6. 新 SDK CI 前提及脚本错误：无 skip 的 SDK 单例交既有 Mac 安装步骤强制执行；真实安装器接口和最外层默认 FAILED 回执已复核。测试工具仅来自原声明的 dev 依赖，CI 安装前后必须保 installed app 字节、路径和原分发版本，不覆盖项目 wheel。
7. 子进程结束到私有完成桥之间取消仍可迟到 saved：桥逐次检查并组合取消信号；Host 在原锁内精确绑定同任务已接受取消，保旧 saved、未知与禁止重试语义。

## 实际结果与执行版本

| 检查 | 实际结果 | 版本／边界 |
| --- | --- | --- |
| 整批源码审查 | 197 文件 Approved，原取消 P2 关闭 | 基线到 `e411f3aa`；真实 CI 不在批准内 |
| 完整 Node 联合回归 | 1543 PASS，0 FAIL，0 SKIP；138.12 秒 | 实际 `e411f3aa`；日志 `js-final-e411.log`，SHA-256 `737c910163011d6836022e46309c9642009d046b82ba66904c8ac6ce292f7ecd` |
| 原 whole reviewer | Native 顺序 3＋字段 7＝10 PASS；CI 构造 4 PASS；Node 70 PASS，0 skip | 实际 `e411f3aa`；首轮缺 SDK 环境的日志不作为最终通过 |
| 取消独立 SPEC | 字段 7 PASS；桥／child-close 12 PASS | 实际 `e411f3aa` |
| 取消 Python QUALITY | 字段与旧 reconcile 10 PASS；5 个 Python 格式检查 PASS | 实际 `e411f3aa`；未重复 Native 矩阵 |
| 取消 JS QUALITY | 桥／工具 51 PASS；Mac CI 合同 1 PASS；5 项语法 PASS，0 skip | 实际 `e411f3aa` |
| 实现者 Native／SDK／字段 | 14 PASS，101.10 秒；旧链 8 PASS，90.21 秒 | 实际 `e411f3aa`；不合计为独立用例数 |
| Root 历史／导入／literal／资源 | 42 PASS，327.48 秒 | 实际 `e411f3aa`，`python-batch4.log` |
| Router 协议／本机集成 | 187 PASS、1 个原 Windows runner 条件 skip；15.04 秒 | `e411f3aa` 产品；仅元数据文件待提交，未更改产品／测试 |
| Router 服务管理 | 349 PASS，3.76 秒 | `e411f3aa` 产品；`python-batch6.log` |
| Router 完整 API | 213 PASS，0 FAIL／ERROR／SKIP；22 进程合计 832.13 秒 | `e411f3aa` 产品；完整 node ID 顺序、各批 JUnit、源码指纹和原始日志 hash 逐项核验，见 `api-final-verification.json` |
| Root 依赖／Host 执行／格式 | 50 PASS，180.81 秒 | 实际 `60c6539`，不改记为新候选运行 |
| Root 首组 10 模块 | 535 PASS、3 FAIL，710.15 秒 | 实际 `fca98f25`；三失败在 `e919` 精确修复并目标复验，原失败保留 |
| Root 四方法模块 | 39 PASS、1 FAIL，246.39 秒 | 实际 `60c6539`；缺 Node override／SDK 前提在后继修复，原失败保留 |

根日志目录：`logs/seek-packs-root-integration-20261028/`。各 slice 的实际执行 SHA、格式检查、独立审批、原 RED 和 GREEN 均保留对应报告／日志，不把所有计数相加、不伪改执行版本。

## Router 与平台门

完整 197 文件 Router 为 Git-bound plan v4／L4。原 Project Constraints、Research Web Checks、同候选 macos-14 Bootstrap 保留；Windows 验证交相应设备，不从 Mac dispatch Windows／Linux 产品任务。

本地 Node 门已包含在上述完整联合回归。文档治理、Python 索引、更新生成页后的架构检查通过；README 复核回执按实际范围补齐。协议、本机集成、服务管理和完整 API 门已通过。平台任务与总体验收分别记录，他平台未执行保留 NOT_RUN；同候选 Mac CI 未取得，hostAcceptance 仍为 BLOCKED，不把本地门通过记作本平台全部验收完成。

API 首次整模块执行因临时材料容量估计不足触发 ENOSPC，pytest 与 wrapper 已退出，最终回执当时未能创建；该次保持 NOT_PASS。其 164 个已登记子树、116498 份常规文件共 4600574501 字节，经增量 gzipCAS 归档、逐文件实际恢复及 inode／哈希／空闲复核后才回收，必要证据保留约 397 MB。没有发信号给生产或未知进程，也未清理其他任务资源。

API 重新收集完整 213 个 node ID，以每批最多十个执行；22 批全部通过。每批保留 JUnit、前后源码指纹及记录，完成范围和结果核对后归档、逐文件实际恢复核验、回收与压缩。启动需至少 3 GiB，运行低于 2 GiB 对本任务 Popen 发 SIGINT 并保留失败。最终控制器 exit 0／progress PASS，独立复核全部 213 个 JUnit case 与收集顺序完全一致、无重复／遗漏和 fail／error／skip；22 批退休回执均 cleaned，原始日志 SHA-256 均匹配。收集与各批源码指纹为 `3faf8263cc8de9d92e52e8c3d0634709c9f47789203d5f9672ed608d69898e9b`。

实际执行源码固定为 `e411f3aaa7a311a7f59e16cd59d0cf9023e6beab`。随后仅提交本报告、总报告、README 复核及生成页等五个元数据文件；产品与测试字节等价，不把元数据提交 SHA 说成重新运行产品测试的 SHA。完整 Node（138.12 秒）、协议／本机集成同一进程（15.04 秒）、服务管理（3.76 秒）、API 22 进程（832.13 秒）合计 989.05 秒；重叠 Router gate 共用日志，只计一次实际进程时间。最终 plan v4／localReceipt v3 在 `logs/seek-packs-root-integration-20261028/`，提交后绑定元数据候选，后续集成候选仍需重新规划、验证及独评。

Mac 原安装步骤强制构建固定 DSH、核 wheel 资源、3081／8088／Doctor，再验证实际 SDK 查询及六组取消顺序；JUnit 必须 exact 7、零失败／错误／跳过。真实 CI 尚未运行，静态合同和模拟控制流不替代干净安装。

MyPy 因既有环境缺 `librt` 保持 NOT_RUN，未安装包或添加 ignore。模型、供应商 live、收费 MCP、正式数据库、常驻部署与其他平台原生均未执行。

## 证据与资源

已登记的测试根在必要日志、完整源／制品／回执归档后，逐文件实际恢复核 SHA 并复核身份／空闲，再仅回收本任务资源。CAS 证据保留所有原始内容与路径／模式／链接元数据，压缩版以 `storage.json` 定位；逐文件恢复不宣称整树同时恢复。原失败和 raw hash 不变。

证据根：`/Users/leon/.codex/backups/rwb-seek-alpha-parity/20261026/seek-parity-20261026-3af31de6/evidence/`。
首批 4 份明确授权 pytest 缓存及临时 CPython 3.14 已收尾；旧未知测试根、其他任务资源、业务数据和常驻服务仍保护。原 Docker daemon 离线导致全局预算收尾 BLOCKED，不能用本批局部测试根 cleaned 替代全任务资源 cleaned。

## 后续范围

剩余 Native／typed 对照分成 34 个有限复用单元，含库内适配、查询与检索代码，不能一概称外部依赖。资金流 code-only 自有查询已有真实原始 fixture 和精确接线准备，但其 live 曾失败，当前未实现／认证新 wrapper；T4 深研／角色、T5 翻译／字符选段／自选与跟踪继续实施。音频相关排除，便民工具后置，原 MCP 凭据、费用及实测授权保持独立。
