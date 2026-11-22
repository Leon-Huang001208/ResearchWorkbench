# 项目固定交付运行时

来源为用户维护的 leon-engineering 0.19.4，提交 `3913ddb9ac612760fb95bf8d8f7102f948c32d0f`。
该提交为固定基础版本；四个未修改文件保留原字节，`iteration-delivery.mjs` 有本项目2026-11-23局部修正：显式已授权的CI修正继续原交付，次数实际累加，不由硬3次门拒绝。没有新增自动重试，也不改变Native调用预算或QA轮次。`manifest.json`明确记录本地修正和全部实际文件校验，不把补修文件冒称上游原字节。
包括原交付控制器、资源适配器、Harness 存储定位、资源内核和其 schema。

项目加载器 `scripts/project_delivery_runtime.mjs` 校验全部文件及路径后加载模块。
校验只依赖仓库内容，错误以 `DELIVERY_RUNTIME_UNVERIFIED` 传播到既有 Git 安全日志。
原交付控制器继续使用 Git common directory 中的交付回执，资源内核继续使用宿主原账本位置，支持旧任务接续。

维护时核验来源提交、更新实际必需的依赖闭包及清单，并运行项目交付、资源生命周期和固定版本回归。
固定代码的更新通过项目评审与 CI 交付；用户级安装器和 Hooks 的启停独立管理。

验证规划使用 `.agents/runtime/leon-engineering/` 中的既有模块。两个固定运行时分别记录各自版本及用途。
