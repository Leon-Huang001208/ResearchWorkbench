# 阶段三：macOS Docker Desktop 实测

## 当前状态（完成 Mac 平台验收）

阶段三 Mac Docker Desktop 任务完成；hostAcceptance PASS，aggregateAcceptance NOT_READY，Windows/Linux 原生及产品 CI NOT_RUN，等待对应设备。阶段一 PR82、阶段二 PR83 已合并。当前任务关联 [PR84](https://github.com/Leon-Huang001208/ResearchWorkbench/pull/84)，合并状态以该实时记录及受管 delivery receipt 为准；未更新日常实例。本报告的提交独立于以下验证候选，历史失败记录保留。

源码候选 `fb9ec4fb978d04caf6e6fca03ba90f49decdd64e`，基线205d2a；[Mac Bootstrap37644483224](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/37644483224) SUCCESS，实际checkout `47f310b648e9d5d9f84cb1bdecd128789f1935b9`，Git父序严格[205,fb9]。正式plan4/receipt3/summary validator PASS，mergeReady/releaseReady false保留总平台门；用户明确授权Mac任务合并，不伪造跨平台ready。

镜像安装源码 `5e1b790b581bca01bc73583a0720b50f664e5941`、实际image `sha256:7dc3942fbddc81f3c4d34d0e860117a086c6cb8a8637eec10624dcd551333ee7`；宿主mac14.6.1/23G93 arm64，Desktop4.94.0/Engine29.8.2，镜像Linuxarm64。最后host stop补丁使镜像中打包的controller字节与最终host不同，不称current-source镜像构建PASS；实际容器Supervisor/DSH/Web/healthcheck/依赖/Compose执行输入不变，精确scoped reuse档案证明差异只用于宿主。

实际安装、authenticated双服务ready、Doctor与四项HTTP200；最新宿主restart16.773s、stop1.953s、owned down/up及容器文件SHA保留PASS。真实Chrome11步通过、Settings架构入口/图返回/API分类/固定版本docs/source/test链接200。最终stop2.962s、owned容器移除、IPv4/IPv6端口18092/13086实际绑定释放，测试data/credentials保留，foreign未操作。

10个local gates PASS；新Python controller168PASS、staging48PASS、JS contract14PASS及完整选中closure已归档。Ruff/mypy无新增诊断，旧全文件格式/类型问题不称GREEN。归档plan/receipt/summary/assurance JSON明确证据范围；17份关键证据及SHA清单保留于任务archive。浏览器截图在outputs/research-web-ui-acceptance/docker-bda/documentation，图输入未变，原人工审阅哈希继续复用。

未验证：模型付费生成、厂商数据授权、真实凭据操作、真实产品升级、双已安装模式切换。非Mac严格研究沙箱、Docker宿主Office/Wind/Tabbit及WindowsDocker ACL保留安全边界。没有复制他平台venv/二进制/源码，未派发Windows/Linux产品CI。

## 历史诊断与修复记录


宿主 macOS 14.6.1 / 23G93，arm64；任务类型为平台适配。taskId: task-20261007-bda2aa87e13e，基线 `205d2a170d9ece9c2751e014b63abe326510ab9c`。用户明确目前只有 Mac；Windows/Linux 真机及其 CI 保留 NOT_RUN，不作为本任务完成前置条件。

## 根因与修复

独立真实镜像构建成功，但 DSH 子进程在 runtime_wait 退出1，Web 尚未启动。固定诊断排除了未经证明的私有叶假设；真实只读、无网络 Node probe 显示 YAML 2.9.0 的 `../doc/directives.js` 缺失。`docker/stage_dsh.py` 将任意层级 `doc` 排除，误删 `dist/doc` 运行时代码。修复限定开发目录筛选到包根，保留深层 runtime，继续排除明确 Git/cache 元数据；不放宽包图、路径、alias/no-follow、哈希、凭据、UID 或沙箱。

已取得失败镜像身份 `sha256:0d5686fcb7753b33b8b9b95cc0524cfff8b5841acc371a51626747131f290425` 的真实导入 RED，合成 fixture 也先 RED 后修。后续新镜像、实际安装/Doctor/重启/持久化/端口释放结果尚待执行，不把构建成功标为产品健康。

## 验收边界

测试仅操作本任务独立 data/state/credentials 与回环端口18092/13086；旧 Native 验证实例为18091/13085，均不属于日常生产实例。既有 foreign Docker 容器61066、端口57444保持未操作。

真实网络运输使用既有无凭据回环代理；所有命令是真实 `run_bounded`，限时和输出上限保持。quiet build 只减少构建进度输出，依赖锁、固定 DSH/Node/Python、CA/签名/哈希仍验证。源 HTTP 大包失败已由 HTTPS 源修复；未关闭安全检查或替换厂商凭据。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"修复发布载荷遗漏，并将Docker临时状态由bind改为私有tmpfs。部署图以模式独立状态节点表达该边界，未声明state bind；Native双进程、Docker单容器两服务、共享研究数据、私有凭据与端口拓扑保持。","diagrams":[]} -->

当时 hostAcceptance: NOT_RUN；aggregateAcceptance: NOT_READY；尚未发布本任务修复或更新生产实例。阶段二/Native 已合并与通过的证据独立归档，不能借为本任务 Docker PASS。

## 第二项实测故障：Desktop 属性视图

YAML修复后最终镜像7ab5进入runtime_probe，原目录exit verify拒绝state bind根uid/gid视图从10001刷新为0。无写等待/普通原子标记不复现，同UID Node只读stat精确复现；dev/inode/mode不变，私有叶仍10001:10001/700。已在独立scratch证明固定fd上的nofollow dot stat使属性视图同步，随后原guard及Node stat都通过。补丁只在固定bind根初始化同步，所有原安全属性仍逐项一致且不授予例外。88合同PASS，独立Python审查无阻塞；整体新镜像生命周期仍待实际验收，不记录PASS。


## 挂载方案实测修正

完整安装证明一次属性同步不能防止 Desktop 根属性再次刷新，d292 同步方案未通过产品启动，不能作为已修复证据。独立 scratch 保留原 Supervisor、real_probe、guard、UID 和安全选项，仅将 `/state` 分别改为私有 tmpfs 与专属 named volume，两者均 runtime/web health_ready、持续60秒、原 healthcheck exit0、shutdown_complete；精确删除各自实例，未操作 foreign。产品选择临时 tmpfs；正式 publicInstaller、持久数据与生命周期验收尚未执行。实验日志为 `/private/tmp/rwb-bind-diagnosis-be41b79cac1441158bf1268673b9dff2/diagnostic.log` 与 `/private/tmp/rwb-bind-diagnosis-93a36baca72444898c88e62de61b5f14/diagnostic.log`。


## Engine tmpfs 表示校准

最终镜像构建成功；公开安装在归属核验处失败。真实 Engine 29.8.2 将三项 tmpfs 完整登记在 HostConfig.Tmpfs，而 Mounts 只列两项持久 bind，先前 fixture 假定 tmpfs 同时出现在 Mounts。失败容器本身健康，但安装未发布成功摘要，不计为公开安装 PASS。核对唯一 installation、image、路径和精确挂载后，仅停止并删除本次容器，数据/凭据保留。控制器将兼容 tmpfs 列表完全省略或完整表示，HostConfig 的固定路径、UID/GID、0700、安全选项和额外挂载拒绝仍强制。


## 生命周期端口释放

快照5e1b790公开安装、Doctor和root/static/index/Atlas HTTP200实际通过。restart在owned容器正常exit0后的10秒严格端口释放截止返回runtime_ports_not_released；稍后无listener且两family实际bindfree。不能将原因未经证实写成TIME_WAIT，也不把该restart记PASS。Mac host controller将默认释放等待改为有界120秒，其它host10秒保持，显式wait_timeout仍生效，port_busy严格reservation检查未改变；新真实绑定/模拟时间合同先RED后GREEN，168controller tests PASS。该补丁仅宿主controller，不改变已接受镜像的实际Supervisor/DSH/Web/凭据/挂载输入；后续复验独立记录运行镜像5e1b与新宿主候选身份。
