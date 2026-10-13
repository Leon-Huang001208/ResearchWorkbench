# Docker 模型凭据修复 · 2026-10-13

## 目标、范围与当前状态

宿主 macOS，功能开发及 Docker Desktop 本机验收。保留现有产品根、业务数据和通用凭据，
为固定 DSH 的两个模型 ref 增加显式 Docker 加密文件存储。不迁移 Native Keychain，不读取
旧 Key，不改研究引擎、模型供应商或公共配置端点。用户选择保留 DeepSeek 官方/deepseek-flash，
允许仅在任务 Docker 工具镜像安装仓库已固定版本的 dev 工具。

实现与目标回归已完成；候选镜像、现有实例升级、用户安全录入 Key、一次真实推理、
同 SHA macOS CI 仍待验证。此报告不宣称整体验收或发布就绪。

## 根因与实现

原 Python 私有 stdio 桥只选择 macOS Keychain，Node provider 也只接受 system-keychain。
Linux 容器因此固定返回 model_credential_backend_unavailable，Host/设置仍健康。

新增 DockerModelStore 复用既有 PrivateFileCredentialBackend 的目录身份、no-follow、
0700/0600、持久 inode 锁与有界文件合同，在现有私有凭据挂载的 models 子目录保存 Fernet
密文。主密钥仅在空模型目录内创建一次，初始化和首写串行化；缺失/损坏密钥或密文失败
关闭，不自动换钥。密文绑定 data-home 命名空间及 ref，两个 ref 独立。主密钥与密文同卷，
不声称抵御同 UID 或管理员。已锁定 cryptography 50.0.1 转为直接归属，版本与 wheel 哈希
不变；Native Keychain 路径、通用凭据和 Host record 保持。

staged Docker 的 owned launcher 显式绑定后端与固定凭据目录，Node 只将非秘密绑定传为
argv，Key 仍仅走私有 stdin。Python Docker 桥的共享 guard/logger 导入使用清理后的 web-prod
环境和已存在只读源码路径，防止加载旧 .env 或创建默认业务目录。

## 架构与结构决策

保留现有 DSH CredentialProvider、固定用途 stdio、Host record 以及既有 Docker 私有凭据
挂载。新增的存储适配不创建执行器、总线、调度或全局凭据中心。图 01 的 Keychain 节点
继续表示 Native 分支，Docker 加密模型记录位于已有私有凭据挂载，不新建图拓扑。
尝试新增图连线的布局校验未通过，已撤回该非必要图改动，未伪造图或视觉回执。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"固定 DSH、Docker 容器、生命周期与私有凭据挂载保留，仅显式绑定该挂载内的模型存储实现。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"保持既有模型配置与显式测试 HTTP 端点、所有权和活动保护，仅增加非秘密存储来源投影。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"沿用 CredentialProvider 和私有 stdio 扩展点、Host record，模型适配不新增引擎或跨边界回退。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"模型存储修复不赋予 Automation 或 Skill 权限，仍由原会话、凭据准入和显式生成边界控制。","diagrams":[]} -->

## 实际证据

- 编辑前 RED：4 个 Docker Python 回归缺实现；Node Docker source 回归失败。普通 API 原状态
  仍显示 Host healthy、credential_code=model_credential_backend_unavailable。
- 最窄 GREEN：Docker 内 221 个模型/私有凭据/启动/平台边界测试通过，2 个 Native 真机
  opt-in 测试 SKIP；16 个模型 API 用例通过；Node 模型 provider 5/5 通过。
- 隔离子进程存取、重建 store、两个 ref、密文绑定、丢失主密钥、并发首次写入及通用凭据
  保留均有合成回归。合成凭据不代表真实供应商证据。
- Ruff、isort 通过；Black 已在任务容器格式化，需最终重检。Mypy 四个源码文件通过。
- 扩大完整 API：56 PASS / 1 FAIL，Word 文件生成返回 document_operation_failed。
  同一失败已在未修改 master cccb778 的同 Docker 工具环境复现；没有改 Word 实现、跳过
  用例或将完整 API 标为 PASS。早期 100/240 秒超时完整保留，扩大至 600 秒得到真实结果。
- 两次只读审查没有发现限定范围内的行为/安全阻断；Python 审查要求的新接口类型标注已补。
  Node 审查的宿主测试不作为 Docker 验收证据，以上计数均由主任务的 Docker 回执提供。

任务工具由 ResourceSession 管理，正常、失败与超时均收尾；日常容器保持当前健康版本。
主 checkout 的 logs/docker-model-credentials-20261013 保存 RED/GREEN、API/基线、审查后的
代码验证、工具构建与每次超时/退出日志。Key/请求体不进入报告或日志，真实供应商不自动重试。

## 未完成项

候选镜像及安装验证、现有数据/凭据保留、用户在设置页安全录入 Key、单次真实生成、
冷重启后配置恢复、当前 SHA 的 macOS 干净安装 CI：NOT_RUN。Windows/Linux 产品 CI
由对应设备交接，NOT_RUN；当前未获推送、PR/合并或其它平台 dispatch 授权。
