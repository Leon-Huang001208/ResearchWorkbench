# 阶段三：macOS Docker Desktop 实测

宿主 macOS 14.6.1 / 23G93，arm64；任务类型为平台适配。taskId: task-20261007-bda2aa87e13e，基线 `205d2a170d9ece9c2751e014b63abe326510ab9c`。用户明确目前只有 Mac；Windows/Linux 真机及其 CI 保留 NOT_RUN，不作为本任务完成前置条件。

## 根因与修复

独立真实镜像构建成功，但 DSH 子进程在 runtime_wait 退出1，Web 尚未启动。固定诊断排除了未经证明的私有叶假设；真实只读、无网络 Node probe 显示 YAML 2.9.0 的 `../doc/directives.js` 缺失。`docker/stage_dsh.py` 将任意层级 `doc` 排除，误删 `dist/doc` 运行时代码。修复限定开发目录筛选到包根，保留深层 runtime，继续排除明确 Git/cache 元数据；不放宽包图、路径、alias/no-follow、哈希、凭据、UID 或沙箱。

已取得失败镜像身份 `sha256:0d5686fcb7753b33b8b9b95cc0524cfff8b5841acc371a51626747131f290425` 的真实导入 RED，合成 fixture 也先 RED 后修。后续新镜像、实际安装/Doctor/重启/持久化/端口释放结果尚待执行，不把构建成功标为产品健康。

## 验收边界

测试仅操作本任务独立 data/state/credentials 与回环端口18092/13086；旧 Native 验证实例为18091/13085，均不属于日常生产实例。既有 foreign Docker 容器61066、端口57444保持未操作。

真实网络运输使用既有无凭据回环代理；所有命令是真实 `run_bounded`，限时和输出上限保持。quiet build 只减少构建进度输出，依赖锁、固定 DSH/Node/Python、CA/签名/哈希仍验证。源 HTTP 大包失败已由 HTTPS 源修复；未关闭安全检查或替换厂商凭据。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"修复镜像依赖发布载荷遗漏，不改变Native双进程与Docker单容器、挂载、认证和文件交付的结构关系。","diagrams":[]} -->

当前 hostAcceptance: NOT_RUN；aggregateAcceptance: NOT_READY；尚未发布本任务修复或更新生产实例。阶段二/Native 已合并与通过的证据独立归档，不能借为本任务 Docker PASS。
