# GitHub Actions 免费额度治理

2026-10-19实际业务证据规范化仅向Research Web Checks既有Python步骤加入test_research_business_evidence.py；无新依赖/job/runner或付费模型调用。实时PUBLIC；最近五次成功run39145940523/39093595410/39092944306/39089784399/39089059111创建至结束574/447/586/578/564秒，均值549.8秒。新定点测试本机不足1秒，预留20秒；保留原20分钟、concurrency和同候选Mac Bootstrap，不发送Windows/Linux产品dispatch。

2026-10-18原生报告修订：test_report_revision.py 加入既有 Research Web Checks Python 步骤，不新增 job、runner 或依赖。当前 PUBLIC；最近五次成功39052893314/39052053211/39046323748/39045609664/39044959112，创建至结束533/637/540/521/523秒，均值550.8秒；新增定点模块本机约0.6秒，预留5秒。Ubuntu仅跳过真实macOS内核例，该例由本机实测，候选安装另经原macOS Bootstrap；不发送Windows/Linux产品验收。

常驻附接回归仅向既有 Research Web Checks Python 步骤增加 test_multiuser_resident.py，无新 job、runner、依赖或 Windows/Linux dispatch。2026-10-17核验仓库 public；最近五个成功 run：39003657366、39002959434、38888413591、38887241312、38886120274（约402/446/404/486/519秒）。

AI资讯零调用测试沿用既有Research Web Checks，固定Node24.19验证原引擎；不新增workflow/job/模型或付费源请求。macOS Bootstrap安装固定锁依赖但不创建数据库；模型与生产切换单独授权。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](research-web-ai-news.md)。

Git主线推进后的原位恢复不触发新workflow或runner；新安全回归沿现有Project Constraints执行。恢复清空旧候选CI/评审资格，必须对最终候选重验；macOS Bootstrap的手动触发及预算门保持。

FinGPT 质量门离线回归进入既有 Research Web Checks Python job；JS 延用 research_web*.test.mjs 清单，仍只有既有标准 runner，不新增 job、Docker/Windows dispatch 或模型费用。Mac 安装沿原 Bootstrap 验证，其他平台交接保持独立。

固定 DSH 搜索升级沿用既有 macOS Bootstrap，只在原生空搜索冒烟中核对 unavailable_count=0；不新增 job、runner 或 Windows/Linux 产品 dispatch。通用检查继续使用既有清单。

resident只读轮询GitHub，不创建workflow或runner。新增resident离线安全用例复用既有Research Web
Checks标准Ubuntu job；macOS安装验证仍用原Bootstrap，不新增Windows/Linux产品dispatch或模型成本。

Claw原生正文搜索的轻量HTTP/协议回归加入既有Research Web Checks Python清单，不新增job、runner或重试。2026-10-15最近五次成功run为38710196645/38708612897/38698113287/38696606443/38692832055，创建至结束约221/232/241/247/236秒；早期搜索回归29项与协议合跑110项本机7.73秒，不将完整API长套件扩入CI。当前仓库public，仍保持原concurrency、超时与平台dispatch边界。

迭代资源收尾的纯stdlib安全测试复用Project Constraints现有标准Ubuntu job，JS身份修补回归复用同一Git safety步骤，不新增workflow或Docker/Windows dispatch。真实受管GC仅在Mac Docker Desktop本机执行并保留证据；CI不访问宿主卷、服务或模型。现有10分钟job上限、concurrency及public/private额度门保持。

Hot 安装器变更进入既有 Mac Bootstrap；该 job 使用 Node 24.19.0，并只验证安装后的
Hot 生产依赖导入，不启动数据库或付费模型。Windows/Linux 产品 dispatch 仍由对应
真机负责，Mac 任务不借新增 Hot 检查扩大它们的自动触发面。

验收预算模块及私有桥接由专属账本/launcher/guard测试进入原验证路由；不新增自动 Docker、Windows 或桌面 dispatch。当前政策过期且不执行模型请求，费用字段不能视为当前报价。

用户已于 2026-10-07 重新开启阶段二、三和跨平台范围。当前宿主按平台职责完成本机验收；Windows/Linux 由对应设备对 exact SHA 接手，缺失保持 NOT_RUN。Ubuntu 通用 CI 继续执行。


本页是 ResearchWorkbench 的 Actions 用量、触发路由和证据保留权威规则。仓库当前为 public；GitHub 官方规则说明，公开仓库使用标准 GitHub-hosted runner 不消耗付费分钟。仓库仍不配置付款方式或付费超额预算，也不使用 self-hosted runner。若仓库以后改回 private、使用 larger runner 或出现其他计费面，立即恢复下述额度状态门。[GitHub Actions 计费规则](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

## 状态门

GitHub Free 的私有仓库每个计费周期共享 2,000 分钟；这不是当前 public 仓库标准 runner 的计费上限。为了控制排队时间、失败重跑和未来转回 private 的风险，内部仍采用保守权重：Linux `1`、Windows `2`、macOS `11`。

| 状态 | 条件 | 允许的远端动作 |
| --- | --- | --- |
| public-standard | public 仓库且只用标准 GitHub-hosted runner | 按路径路由运行自动门禁；仍记录实际耗时 |
| normal | 使用量低于 50% | 按路径路由运行自动门禁 |
| watch | 50%–69% | 检查重复运行和最近 5 次耗时 |
| constrained | 70%–84% | 非必要跨平台验证改为手动 |
| critical | 85%–94% | 只运行阻断发布的原生门禁 |
| frozen | ≥95% 或 billing-blocked | 禁止 push、merge、tag、rerun、dispatch、publish 和 cleanup |

`normal` 至 `frozen` 的百分比阈值只适用于 private／billable 状态。`frozen` 期间允许本地只读、本地编辑、本地测试、本地提交和隔离 workspace。恢复条件是当前 Billing 页面或 API 明确显示新周期额度已重置，或 GitHub API 明确证明仓库已变为 public 且当前标准 runner run 能正常启动；预计日期、邮件或旧截图都不是恢复证据。安全紧急修复也需要用户重新明确授权。

## 月度分配

- 50%：Ubuntu 日常测试、文档和项目约束。
- 25%：必要的 macOS／Windows 安装及平台合同。
- 25%：发布、修复、失败重跑和不可预期储备。

准备任何原生平台 workflow 前，记录最近 5 次成功运行的实际平台耗时，并使用上述权重估算。达到下一阈值后立即应用更严格状态，不以“本次应该很快”为例外。

## Workflow 路由

| 改动 | 自动门禁 / Windows 验证责任 | 不应触发 |
| --- | --- | --- |
| 文档、归档、报告 | Project Constraints（Ubuntu） | Bootstrap、Windows、Desktop、Tabbit |
| 普通 Research Web／CLI | Research Web Checks（Ubuntu） | Bootstrap、Desktop；非 Windows 专属时不跑 Windows Verify |
| 共享安装器、Web 锁、固定 DSH/CJPY、跨平台 runtime/服务装配 | 自动 Research Web Checks + Bootstrap；Windows 真机对 exact SHA dispatch Windows Verify | Desktop |
| macOS shell launcher | Research Web Checks + Bootstrap | Windows、Desktop |
| Windows launcher、路径、认证文件、本机集成、编码/进程/服务管理 | 自动 Research Web Checks；Windows 真机对 exact SHA dispatch Windows Verify | Bootstrap、Desktop |
| Docker 打包、共享运行时契约/控制器、容器认证与凭据边界 | Linux 真机对 exact SHA dispatch Research Web Docker（Ubuntu，amd64/arm64）；共享 Native 合同仍进入 Bootstrap | 普通文档/UI 不触发 Docker；不代替 Native 或 Desktop |
| Tabbit 平台合同 | 用户显式 `workflow_dispatch` | 普通 push／PR 自动触发 |
| 桌面专属路径 | Desktop Verify | 普通 Web workflow 不能替代桌面门禁 |
| Desktop Release | tag 或显式 dispatch | 普通 push |

Project Constraints 保持所有 PR 和 `master` push 自动执行；自动 workflow 必须设置 concurrency、`cancel-in-progress: true` 和明确超时。Research Web Bootstrap 只运行 `macos-14`。Windows Web workflow 只保留 `workflow_dispatch`：policy 对 platform-sensitive changed set 选择 Windows gate 后，Windows 真机 checkout 待验 ref，以该机 `git rev-parse HEAD` 得到的 exact SHA 发起 `windows-2022`。Mac PR/push 不触发 Windows workflow。普通 UI、文档、纯 framework/DataHub 业务代码不选择 Windows gate。Windows workflow 未选择时是 `NOT_REQUIRED`，已选择但未从 Windows 真机执行时是 `NOT_RUN`，均不得写成 `PASS`；Windows GitHub CI 也不能替代同一或另一 Windows 真机上的安装、升级、真实用户目录或 Office/Wind 验证。这一 Web 路由边界不改变 Desktop Verify 的独立原生双平台规则。
Windows job 在 clean checkout 上执行公开 `setup-web.cmd --no-start`、`rwb.cmd` start/doctor/stop、setup contracts、local-integration contracts 和 loopback smoke；路径触发本身不能替代这些真实 job steps。
Research Web Checks 的 Python 部分固定为协议、集成协调、文档服务、文档同步与 CLI 懒加载合同，JavaScript 部分运行 `research_web*.test.mjs`。完整 `tests/research_web/` 仍在本地交付或高风险变更中按影响面运行，不能偷偷扩进日常 workflow；需要扩大自动测试时先以最近 5 次成功耗时重新评估额度。

验证策略、只读规划器、薄兼容入口及其治理文档属于项目治理变更，只进入 Project Constraints。规划器输出的是待执行计划，不会自行触发 Actions；`full-delivery` 只声明交付强度，实际远端动作仍由受管交付控制器和本页状态门决定。

RWB Git 安全入口的临时仓库测试在现有 Project Constraints 的独立步骤运行，使用该 job 的标准 Ubuntu runner、既有 concurrency 与 10 分钟上限，不新增 workflow 或原生平台 job。它验证 Git 对象恢复、备份与清理算法，不代表 Linux 产品或其他宿主启用。macOS 受管入口在 push、合并及远端分支清理前重新核对当前 visibility 和标准 runner 运行证据；private／billable 状态没有当前额度证明时停止远端动作，不沿用历史 public 结论。当前 RWB 不开启 GitHub Auto-merge，入口在检查及评审满足后执行普通 PR Merge，不修改仓库设置。

Docker 路由的专项例外是 `.agents/verification-policy.json`、`tests/javascript/verification_policy.test.mjs` 及 Docker/额度契约测试：它们仍选择容器验收门，交接给 Linux 真机对 exact SHA 手动发起，防止门禁 ID 与实际工作流脱节。门禁 ID 为 `.github/workflows/research-web-docker.yml#docker-runtime`。普通治理文档、产品文档和 UI 仍不触发 Docker。

Research Web Docker 使用标准 `ubuntu-24.04`，两个矩阵项 `linux/amd64`、`linux/arm64` 串行执行（`max-parallel: 1`），每项最多 60 分钟；仅 arm64 设置 QEMU，Buildx 只加载本机镜像、不推送 registry。按提交与架构唯一标记镜像，构建前验证 Dockerfile 与共享运行时版本锁一致。不从 PR/push 自动触发；Linux 真机完成本机验收后 checkout 待验提交，以 `git rev-parse HEAD` 获取 exact SHA，发起 `workflow_dispatch` 并传入必填 `expected_sha`。checkout HEAD 与 `GITHUB_SHA` 均须等于该 SHA，否则在构建前失败关闭。取消同 ref 的旧运行；两个矩阵项最多使用 120 Linux runner 分钟，不配置外部缓存或扩大 runner。

容器门执行 Compose 校验、镜像构建、8088 Web 与容器内 3081 认证健康、重启、非秘密数据跨 down/up 持久化、最终 down 与宿主端口释放；每项使用独立临时 data/state/credential 挂载，最后清理。它证明 Linux 镜像行为，不能替代 GitHub macOS Native Bootstrap，也不证明 Windows Native、Docker Desktop 集成或桌面产品。首次远端运行前，本地静态合同通过不等同于两架构构建和运行已通过。

## 平台验收责任

文档安全路由改动的 macOS 任务可对最终候选使用现有 Bootstrap 手动入口取得干净安装、固定 DSH、服务健康与 Doctor 证据，另保留本地文档路由/浏览器结果。此补充不扩大 docs-only 的自动触发面，不把 Ubuntu 文档门算作 macOS CI；dispatch 仍需独立明确授权。

上述表格描述现有自动触发配置，不授予 Mac 任务 Linux/Windows 适配或验收责任。24GB Mac mini 负责项目主开发、Docker 构建/测试、常驻服务、本机 macOS 验收及 GitHub macOS CI；MacBook Pro 作为受控远程操作与浏览器入口。Windows/Linux 真机任务分别负责本平台适配、本机验收及对应 GitHub CI，不承担功能开发。Ubuntu 的 Project Constraints/Research Web Checks 结果属于 Linux CI，不能作为 macOS CI 证据，也不得要求 Mac 任务修复或等待其平台适配才能完成。

其他平台的 CI 自动启动时，保留状态并交接对应真机任务；本平台未取得所需 CI 时仍不能宣称本平台验收通过。跨平台发布就绪继续要求各目标平台证据。验收范围和任务状态记录以 [Agent 任务路由指南](AGENT_WORKFLOW.md) 为准。Docker workflow 已改为 Linux 真机 exact-SHA 手动入口；其余自动触发配置、runner、费用状态门和发布授权不变。

## Artifact 与保留期

- Bootstrap 成功上传 `doctor.json`、`connections.json`、首页 `root.html` 和主静态模块 `app.mjs`，证明干净 runner 的安装/产品 ready 与页面资源可读取；完整 `logs/setup-web.log` 只在失败时上传。
- Bootstrap 和 Windows Verify 的任务 artifact 保留 3 天。
- Docker 成功 artifact 只含固定字段的健康摘要、Compose 服务名及固定阶段/数字退出码；失败 artifact 保留经过秘密模式扫描的固定事件分类计数，并附同样的阶段/退出码 JSON。启动失败还可保留最多 16 条精确五字段摘要（固定阶段、受控异常类别、errno、runtime/web 退出码），只接受白名单与有界整数。全部原始行被省略，原始 build/runtime/container 日志和凭据目录不上传。Docker artifact 保留 3 天。
- GitHub 仓库默认 Actions artifact/log retention 由仓库所有者设为 7 天；该设置不由本地代码自动修改。
- 若账户仍有 private 仓库或其他 included-usage 消耗，在 Billing 的 budgets/alerts 中启用 90% 与 100% 邮件提醒，但不得创建正额度预算、付款方式或允许付费超额。将提醒状态与仓库默认保留期一起记入月度记录。
- 每月记录总用量、各 workflow 次数、失败重跑数、平台耗时、估算权重和剩余额度。

## 当前状态与恢复证据

2026-09-17 先观测到 private 状态下 2,000 / 2,000 included minutes 和 billing-blocked，随后通过 GitHub API 确认仓库已改为 `PUBLIC`。提交 `76d1ea1053187569bb23d30f9a22b894ccbc0675` 的 Project Constraints、Research Web Checks 和 Bootstrap 双平台均正常启动并通过；repair 提交 `de39abcdbf3551c9985615e4cf80cd121a3a16b3` 的 Project Constraints、Research Web Checks 和 Windows Verify 也通过。因此当前状态是 `public-standard`，旧 billing-blocked 只作为历史证据保留，不再冻结标准 runner。

docs-only 提交只能创建 Project Constraints。若出现 Research Web Checks、Bootstrap、Windows、Tabbit 或 Desktop run，视为路由回归。平台敏感提交则以 `.agents/verification-policy.json` 和 workflow path 合同共同决定 Ubuntu、macOS、Windows 或真实设备责任，不从历史 run 推断当前 gate 已通过。

## 月度记录模板

```text
周期：YYYY-MM-DD → YYYY-MM-DD
仓库 visibility：public | private
计费状态：public-standard | metered
included usage（不适用时填 N/A）：____ / 2,000
Ubuntu：____ runs / ____ minutes
Windows：____ runs / ____ minutes
macOS：____ runs / ____ minutes
失败重跑：____
artifact storage：____ / 0.5 GB
当前状态：public-standard | normal | watch | constrained | critical | frozen
决定与原因：____
```

Host元数据专项升级测试复用Research Web Checks现有test_resident.py；resident路径由现有Mac Bootstrap自动选中，不新增job或平台dispatch。只校验macOS清洁安装/固定DSH/健康/Doctor，不调用模型。

通用Python回归的报告渲染器依赖直接抽取现有 requirements/web.lock 中的 ReportLab 固定版本及哈希，仅补足原通用 dev 环境缺项；不新增产品依赖或 runner。测试凭据使用进程内夹具，不依赖Linux系统凭据库。

2026-10-17私网多用户增加四个定点身份/网关/运行池/CLI测试文件到原Research Web Checks步骤，
不增加job、runner、依赖或平台dispatch。变更前实时仓库PUBLIC；最近五次成功run
38888413591、38887241312、38886120274、38878187740、38876906340的总时长分别
404、486、519、442、510秒（含准备/安装，均值472.2秒）。本地四个新模块约8秒，
预算预留新增30秒，沿用20分钟超时及既有concurrency；实际CI时长仍由候选run记录。

2026-10-18报告质量修复：向Research Web Checks原Python步骤加入calculation、quality_scope、delivery_cache三个定点模块；不扩为全目录、不增加job/runner/模型请求。当前仓库PUBLIC。最近五个成功run 39046323748/39045609664/39044959112/39044358075/39026388921，创建至结束540/521/523/392/494秒，均值494秒。本机计算模块约0.2秒、scope两例6.45秒，新增预算15秒；保留原20分钟、concurrency和macOS安装独立验收，纯缓存测试不作为Linux/Windows产品原生证据。
