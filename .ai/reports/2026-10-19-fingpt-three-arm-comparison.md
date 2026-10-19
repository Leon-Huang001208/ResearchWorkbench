# FinGPT 三组隔离比较与安全收尾

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅增加默认关闭的本机验收控制器与原收尾入口的窄身份恢复；生产部署、DSH默认执行、账号与数据流保持。实验不构成新的生产研究节点，原部署图仍适用。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"独立case执行已授权三组实验并复用既有CI与资源入口；原验收和安全交付图仍适用，源码、文档和测试清单已同步。","diagrams":[]} -->

宿主macOS，功能开发；Mac本地与同候选MacCI验收，Windows/Linux产品交接NOT_RUN。
用户已批准A当前DSH+Flash、B原267a Node+Flash、C原267a Node+Lite，各一次，截止2026-10-16。

## 实现与真实边界

- 原题、提交和代码归档固定；数据、端口和Lite Keychain namespace独立，生产Flash仅固定只读seam。
- 仅静态设置页可匿名读取；Cookie/Origin保护设置，配置保存不生成。执行scope评审、全部零生成预检和持久预约共同阻止提前或重复研究。
- 48工具/6检索覆盖DataHub别名；进程组退役验证父进程已退出的后代，独立deadline不等待主HTTP。
- 原始源响应与报告只读审计，未知usage及缺失质量/格式/版本不伪造。原引擎完整研究步骤、工具结果不替换。
- 缓存重建补登记保留旧回收证明和身份，只认可匹配tracked源码的真实pyc及空目录，未知内容/并发新增阻止删除。

## 当前验证检查点

定点27Python、5Node已通过；评审发现的模板导出、检索别名、进程组、deadline和未知文件竞争问题已修正，A预检另补真实凭据/provider/model/health硬门。最终本地Router、打包/CI、最终SHA评审及真实三组仍待后续证据。Lite未配置时全序列保持BLOCKED，不以准备完成冒充研究成功。
