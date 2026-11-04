# 生命周期桥 CLI 顶层等待修复

- 宿主 macOS；任务类型为项目管理面最小缺陷修复，隔离 worktree。本机只运行 Node 24.22.1 及真实临时 Git/v2 恢复、临时内核 store；无产品/平台功能扩展、依赖或全局改动。
- 根因：真实 CLI 以 `git_safety.mjs` 为入口并顶层 `await runDelivery()`；pending 恢复路径再动态 `await import('./git_safety.mjs')`，等待同一尚未完成的模块求值，Node 以 13 退出并报告 unsettled top-level await。此前 import-mode 回归不能覆盖这个入口。
- 最小源码修复仅为 `resource_lifecycle.mjs` 静态具名导入同一 `validateCloseoutRecovery`，移除调用处动态自导入。没有修改 Git 安全模块源码，没有注入可替换验证器或绕过任何证明、引用、路径及保护门。
- 架构复核：ESM 环内仅建立函数/常量，桥模块求值时不调用验证器。函数声明的 live binding 已建立，CLI 调用发生在安全模块的常量初始化之后，不形成 TDZ 或异步自等待。没有新增运行节点、权限或第二校验流程。

## 实际验证

- RED：`node --test --test-name-pattern='CLI pending recovery' tests/javascript/git_safety.test.mjs`，真实子进程 `argv[1]` 为复制但未改写的生产 `git_safety.mjs`，原 pending 证明由真实临时 Git/v2 正式恢复 API 生成。实际退出码 13，stderr 明确指向 `git_safety.mjs:2197` 的 unsettled top-level await。日志：`logs/lifecycle-cli-entrypoint-red.log`。
- GREEN：同一测试退出 0；其 CLI 子进程正常返回 2 / `cleanup_pending` / `ENOENT`，表示完整恢复验证通过后到达有意缺少的临时运行时 manifest。测试只合成控制器的只读远端边界，完整恢复验证器没有替换；不是假入口 driver，不执行真实 runtime/event。原 pending 字节不变。日志：`logs/lifecycle-cli-entrypoint-green.log`。
- CLI 与原 module-mode 证书目标 17 项通过、0 失败，exit 0；其中 CLI 错候选恢复证书仍以 1 / `CLOSEOUT_FINALIZATION_UNVERIFIED` 拒绝，没有顶层等待警告。日志：`logs/lifecycle-cli-entrypoint-and-recovery.log`。
- 测试同时保留生产 CLI 的宿主门：非 macOS 的真实子进程只能断言原 `HOST_UNSUPPORTED`，不伪造 platform、不跳过门，也不冒充 Mac CLI 验收。本机最终 Mac 分支两项通过（`logs/lifecycle-cli-entrypoint-host-contract.log`）；非 Mac 分支仍由对应 CI/宿主另证。
- 最终 JavaScript 只读评审专门核对 CLI 顶层 await、循环依赖和初始化顺序，未发现新 P1/P2；两修改文件的 Node 24.22.1 语法检查通过。
- 完整四套相邻回归加真实内核合同：Node 24.22.1 执行 `node --test tests/javascript/git_safety.test.mjs tests/javascript/git_safety_amend_prepared.test.mjs tests/javascript/iteration_closeout.test.mjs tests/javascript/resource_lifecycle.test.mjs tests/javascript/fixtures/resource_lifecycle_kernel_contract.mjs`，**279 项通过、0 失败，exit 0，317580.077417 ms**。日志：`logs/lifecycle-cli-node24-final-neighbors-and-kernel.log`。

## 边界

- 不执行工作区 Git 写入、远端 CI、真实宿主 lifecycle 注册/事件、旧任务收尾或生产操作。没有改旧 proof/回执、全局运行时、安装依赖或调用模型。
- 子进程读取临时 HOME 的只读控制器；运行时 manifest 有意缺失，因此该回归证明真实入口不再挂起及恢复门不变，不宣称现场生命周期已 cleaned。
- 固定 Node 24.19 的 CI 与新候选远端交付由主代理另行留证。Windows/Linux Native、Docker 与真实现场恢复为 NOT_RUN。
