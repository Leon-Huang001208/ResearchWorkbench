# macOS 双运行时端口分配设计

## 范围与批准来源

用户于2026-10-06明确当前只支持macOS，并在端口/代理诊断说明后要求“执行”。本设计延续其已批准的方向：保留8088/3081默认兼容，冲突时使用空闲端口，记录真实端点并安全释放本实例资源。仅修改现有Web Native/Docker运行路径；不重做既有Task1–12、不引入第二产品/依赖清单、桌面/Tauri或新验收框架。Windows/Linux宿主验收延期，不改写为通过。

源码基线05326b6066f96a572db4ac87f3bdc041ff92003f，隔离分支codex/macos-runtime-port-allocation-20261006。没有授权push、PR变更、merge、dispatch/rerun、发布、全局网络/Harness/Docker配置修改或停止日常服务。

## 方案选择

1. 只提供显式端口参数：改动少，但不能满足用户要求的自动避让。
2. 默认优先、冲突自动分配、记录实际端点：推荐。保持已有地址兼容，并让不同数据根的隔离实例并行运行。
3. 每次无条件随机端口：容易改变浏览器地址和可信回调origin，不采用。

## 端口策略

- Native默认Web8088、DSH3081；已成功使用的端口优先复用。首次启动或已证明旧实例退出后，默认端口被其他实例占用时，有界分配空闲回环端口。
- Docker仅选择宿主Web发布端口；容器内Web8088/DSH3081保持固定，DSH不发布至宿主。宿主3081的无关监听不是Docker端口冲突或停止失败。
- 公开安装器和rwb启动入口接受显式Web/Native Runtime端口；显式指定被占用时返回稳定错误，不悄悄改变用户指定值。自动分配采用操作系统分配候选与有界绑定失败重试，不将“曾经检查为空闲”当作成功绑定。
- 端口必须为严格整数、范围有效、Native两端口不同，不能开放公网绑定。原有无参数调用仍优先采用默认端口。
- 在目标安装生命周期锁内分配。只有目标数据根已证明无活动写入、冲突来自其他实例或全新隔离数据根时才自动避让。损坏、foreign或unknown运行记录仍失败关闭，不能通过换端口绕过归属检查。

## 状态与生命周期

现有Native run/web.json、run/runtime.json保存实际端口、PID、argv指纹和进程启动身份；Docker核对真实NetworkSettings.Ports。增加私有、严格schema、无alias、原子写入的端点记录，不把端口塞进旧runtime.json v1而破坏其精确字段校验。旧安装无新记录时按已验证账本或旧默认合同读取。

status、Doctor、logs、restart、stop、浏览器URL和两模式切换均从已核验的实际端点构造管理器。损坏或与进程/容器事实矛盾的记录不回退为默认端口。只有真实健康后发布成功端点；失败保留旧成功记录并仅清理本次再次验证为owned的进程树/容器。重试前先证明前次对象已退出。停止后确认本实例监听消失，不把无关进程占有某个旧端口当作应杀掉的对象。

保留immutable image、installation/挂载/launch label归属与原有活动研究保护；同一研究数据根仍不能被两模式同时写入。自动选端口不授予进程接管或用户数据覆盖权限。

## 新发现的可信origin边界（实施前需确认）

当前共享研究根的.control/datahub.json与.control/mcp-runtime.json均存内部控制token及可信BFF URL，并拒绝URL漂移。DataHub Python/JS每次读取，MCP adapter在DSH启动时读取；只改端口会导致其中一个初始化失败。

推荐保留两份文件及消费路径，不移动、复制或轮换token。仅在旧Web/DSH或容器均已验证退出且新模式未运行时，在启动事务中验证旧URL、私有权限、schema、单链接和原文件身份；Native重绑定到实际Web回环origin，Docker重绑定到容器内部127.0.0.1:8088，与宿主发布端口无关。两份记录一致后才启动消费者。

必须保留原token及全部其他有效字段，默认origin未变时不写文件；mode选择与--no-start本身不重绑定。第二份写入或目标启动失败时，只在本事务写入的内容/身份仍匹配且运行时已静止时回滚；遇到未知并发替换则拒绝覆盖，报告恢复未验证。持久事务标记应支持中断检测，不能在崩溃后把半完成重绑定当成功。真实供应商凭据、Keyring及Docker文件凭据不迁移。

这是端口变更所需的内部认证配置行为变化，不是放宽URL校验；在书面设计确认前不实施该部分。

## 验收

TDD覆盖默认空闲/占用、显式冲突、绑定竞争、读写畸形/alias记录、真实端点恢复、foreign实例保留、失败精确回滚、Docker宿主3081占用不误判、发布端口不符拒绝及释放本实例端口。DataHub/MCP两份origin与token在Native动态端口→Docker→Native往返一致，业务数据fixture不变；第二份写入失败、崩溃中断和并发替换反例必须失败关闭。

沿用项目policy/planner/receipt，以本次完整changed set选择最小充分闭包；同步安装、生命周期、模块、架构inventory和生成索引文档。macOS真实测试使用私有数据和状态，不停止日常8088/3081实例；保留默认入口兼容测试。未执行的远端或跨平台门保持实际状态，macOS阶段结论独立记录。

## 镜像网络实测（本轮已完成）

未修改全局代理配置。正常Docker Desktop实际拉取node:24.19.0-bookworm-slim和python:3.12.13-slim-bookworm均exit0。

- Node digest: sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df
- Python digest: sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2

这证明固定基础镜像获取链路可用，不证明APT/npm/pnpm/DSH构建、最终镜像或容器生命周期已通过。旧CLI manifest直连超时不再被用作Desktop无法拉取镜像的证明。
