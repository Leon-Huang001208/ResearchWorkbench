# PR96 与 master 双格式模型凭据兼容复核

宿主 macOS / 功能修复；本机范围为合成文件、私有 bridge、源码契约和测试，不证明 Linux 真机、Docker 镜像或供应商生成。

- 隔离 worktree：`/Users/leon/.codex/worktrees/pr96-review-20261014/ResearchWorkbench`。
- 分支：`codex/pr96-review-20261014`；原 PR96 head `85831c7d70c89fb86fff4b220b5598aa1fe6c67c`；普通 merge master `0cf38ff23f72b9537ca4a09616115ec1cc50d979`，未 rebase/force-push。
- 复现 11 个内容冲突。保留 master Native Keychain、Fernet `DockerModelStore`、历史模式、FinGPT/Claw 与原 Host record；保留 PR96 管理器初始化、探针、AES-GCM 随机实例及独立只读主密钥卷。
- 唯一私有 bridge 默认 `native-keychain`；常规已认证 staged 源使用 `docker-encrypted-file`；管理器仅显式绑定 `docker-encrypted` 选择 AES-GCM。launcher 额外要求实际 staged selection、固定私有路径、32位实例身份与原有来源/资产校验。
- 混合 backend 参数及两个外来密文格式均拒绝；无 fallback、转换、旧 Key 删除、主密钥重建或覆盖损坏密文。所有请求仍限两个固定 ref 与 resolve/describe/set/unset；stdout 为私有结果，stderr 被桥接吞并，环境清理保持。
- 来源分别为 `system-keychain`、`docker-encrypted-file`、`docker-encrypted`，Settings 如实展示。configured/Doctor 不认证真实生成。
- Fernet 原类仅运行于 Linux 的边界保留。四项纯 POSIX 文件算法测试使用局部 sys.platform 合成条件；真实非 Linux 构造器另测拒绝且零目录创建。Linux 私有 stdio 原用例在 Mac SKIP；两项 Native Keychain/DSH opt-in SKIP，未读取生产 Key。

## 实际本机验证

工具复用已授权 local-models-fusion `.venv/bin/python` 与 `logs/toolchain/node-v24.19.0-darwin-arm64/bin/node`，未安装依赖。Ruff 0.17.0 / Black 26.10.1 / isort 9.0.2 / mypy 2.4.0。

- 焦点 Python：250 PASS / 3 SKIP / 6 个 pytest 历史临时目录清理 warning；凭据两格式、launcher、Docker manager、通用凭据；结果见 `logs/pr96-review/focused-python-final.log`。
- L4 Python：632 PASS / 1 Windows native runner SKIP / 1 个 Starlette anyio 弃用 warning / 266.60秒；container supervisor、service manager、local integrations、protocol、API；结果见 `logs/pr96-review/closure-python.log`。
- Node L4 及相关模型/Docker 契约：135 PASS，见 `logs/pr96-review/closure-node.log`。最后 bridge 参数/操作预拒绝调整复跑7项模型焦点 PASS，见 `focused-node-final.log`。
- changed Python Ruff/Black/isort PASS；mypy 四源文件 PASS，见 `ruff-final.log`、`black-final.log`、`isort-final.log`、`mypy-2.log`。首次 mypy 8个属性类型错误已加显式属性类型修复；未删除失败日志。
- documentation governance、architecture、doc sync、Python生成索引 PASS。正式受管 runtime manifest 逐文件 SHA-256 无 mismatch。Project Constraints 首次 README review 未更新被拒绝，已同步真实复核回执后重跑。
- 两格式互拒覆盖四操作与原记录字节保持；AES 合成坏主密钥四操作拒绝并保持密文。独立实例、wrong-key、identity、alias、权限、故障写/删、clean-env 和禁止全局 Settings 导入均在焦点用例内。

## 限制与原状

Docker 运行、真实 Key、Linux/Windows 真机、模型生成和远端 CI 全部 NOT_RUN，未 push、改 PR、merge远端或 dispatch。新镜像与真实 read-only 布局必须由后续授权设备任务验证；本机算法与桥接测试不替代它们。

原 PR96 worktree tracked/index diff 均 exit0、untracked0；主 checkout tracked/index diff 均 exit0。主 checkout本次读取 status为16条未跟踪项（逐文件72），仅观察既有或其它任务材料，不执行写入。所有本次编辑及提交限隔离 worktree。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"合并保留两既有部署与源验证，管理器显式选AES-GCM；不增加部署节点或迁移。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"两个既有存储复用同一私有四操作bridge与固定ref，Host认证record保持。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"仅区分来源投影，不改变配置/生成接口或活动守卫。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"合并保留主线Claw和FinGPT，不扩大权限或新增编排。","diagrams":[]} -->

最终完整 changed set 为45项（相对 master；含原PR96变更、合并修复、当前报告/计划/回执），清单见同名 plan 的 changedFiles 与本地 `logs/pr96-review/changed-files.txt`。Receipt validator：valid=true，12项本地门PASS，5项CI NOT_RUN，result=BLOCKED、mergeReady=false、releaseReady=false；这一回执不认证远端发布或跨平台就绪。
安装闭包同步核对 web.in/web.lock、setup_web.py、安装说明与Bootstrap workflow；仅保留既有 cryptography 50.0.1 直接依赖注释，无新包/版本/哈希；当前 macOS 干净安装CI仍NOT_RUN。

## 独立质量 P2：外来 AES 树绑定修复

审查复现 A 密文树 + B 完整主密钥/identity + B instance 在原构造器只检查 algorithm 后被误判未配置。先运行四操作拒绝测试：4 FAIL（DID NOT RAISE），证据 `logs/pr96-review/foreign-binding-red.log`；随后收紧专用模型类。构造器在原锁内核验每条已有 JSON 的 canonical 外层 schema/version、完整 envelope/schema/version/instance、固定 service/ref 文件名映射并调用原 AEAD 解密验证。三个公开存取方法也拒绝其他 service/ref；通用 PrivateFile 保留泛用。未读取、转换、删除、重建或迁移任何旧 Key；只处理临时合成测试数据。

全部仓库调用定位未发现专用 AES 类的任意 service/account 调用者或单测；该类是产品固定模型后端，约束不泛化至通用业务凭据类。新回归包括完整 B 绑定四操作拒绝、wrong key、version bool、额外字段、foreign namespace/ref、伪造 instance/文件名但错误 AEAD，以及两个正确旧模型 ref 重开后密文字节不变。错误仍由 `_safe_errors` 记录固定拒绝事件，绝不输出密文/Key/异常正文。

本轮实际验证日志：`foreign-binding-closure.log`（264 PASS / 3 平台与opt-in SKIP；AES/双格式/manager/通用凭据/launcher）、`foreign-node.log`（25 PASS，模型及Docker JS契约）、`foreign-ruff.log` / `foreign-black.log` / `foreign-isort.log`（changed-set检查）、`foreign-mypy.log`（4源文件PASS）。旧 L4 API/服务套件是上一候选证据，本轮不冒称复跑；远端 CI、真实 Docker/供应商/其他设备仍 NOT_RUN。

本轮初次生成索引与architecture同步门拒绝已保留日志；重新生成索引并同步全部 dual-runtime 模块文档后复核，不降低验收要求。
