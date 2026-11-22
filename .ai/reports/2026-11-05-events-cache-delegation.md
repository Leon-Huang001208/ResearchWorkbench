# 单一缓存冻结观察的私有报告委托

- 宿主 macOS；任务为隔离管理面实现，本轮只执行源代码/临时 Git 与临时内核 store 的目标验证。源码交付和真实授权配置/报告由主代理分开留证；没有产品研究功能、HTTP、依赖或全局运行时改动。
- 默认无配置保持原报告行为及结果形状。私有 common 配置严格绑定 owner/reporter root/common 路径、dev/ino、同源 origin SHA、授权元数据、任务及冻结资源回执 SHA/字节。仅 reportCache.project 使用 owner，其他任务 API 继续使用 reporter。
- 配置 0600/当前 uid/单链接/noalias/普通文件/64 KiB 有界 FD 读；冻结回执私有快照限 16 MiB。固定 Git 身份命令清理继承覆盖、禁系统/全局配置和 lazy-fetch/replace，不记录 URL。分项 builders 精确为 desktop-linux/rwb-dev-builder，安全非负整数合计等于 afterBytes。
- 当前 adapter owner/enrollment 及获准冻结观察链在开始及报告前核对；bytes 必须与本任务一致。grant/receipt/identity/origin/owner/链漂移均拒绝且不 event。没有新增 adapter、迁移 owner、CAS、锁或测量。授权文件不是用户许可自证，须由操作者基于明确用户授权建立，不接受 HTTP/库参数 grant。
- 该委托上报路径只复用冻结观测，不执行 Docker 测量、builder maintenance/GC 或服务变化，不声明实时/最新。其他正式交付资源/缓存安全门不变；原 API last-observation 同 owner 读写竞态仍存在，previousBytes/sequence 仅作审计。

## 实际证据

- 主 RED：真实双临时 Git 项目、原单 adapter owner 下，旧桥报 CACHE_ADAPTER_OWNERSHIP_CONFLICT；日志 `logs/cache-delegation-red.log`。
- 主 GREEN：owner 归属报告、任务 API 仍归 reporter，原件回执不变；日志 `logs/cache-delegation-green.log`。
- 独立评审提出观察链范围收紧后，先观察 outside-chain/different-bytes 两个 Missing expected rejection；日志 `logs/cache-delegation-chain-red.log`。补原授权链及当前字节门，不虚构 CAS。
- 最终目标反例及真实内核合同 **68 项通过、0 失败、exit 0**；Node 24.22.1，命令 `node --test tests/javascript/resource_lifecycle.test.mjs tests/javascript/fixtures/resource_lifecycle_kernel_contract.mjs`，实际 wall 6.566 秒、测试报告 6514.57025 ms。日志 `logs/cache-delegation-freeze-targets-and-kernel.log`，完整命令回执 `logs/cache-delegation-freeze-command.json`。
- 三个变更 JS 文件语法检查通过；文档治理检查通过。回执为 `logs/cache-delegation-freeze-static.json`。独立只读评审提出的观察链范围 P2 已闭合，无新 P1/P2。
- 完整四模块加 kernel 闭包待主代理 commit/prepare 后在 exact 候选执行一次；Router/CI/真实配置/实际收尾不以 feature WIP 结果代替。
