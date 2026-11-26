## 从哪个问题开始

使用者先看[快速开始](../../../outputs/research-web-architecture/getting-started.html)和[指南](../../../outputs/research-web-architecture/guide-data.html)。需要理解实现边界、组件职责或代码时，再读这一栏。

## 系统与流程

- [产品与系统边界](../../../outputs/research-web-architecture/00-system-overview.html)：RWB 与研究执行、资料、数据的分工。
- [运行结构与部署](../../../outputs/research-web-architecture/01-deployment.html)：主机、网关、后端和数据位置。
- [组件职责与依赖](../../../outputs/research-web-architecture/02-module-dependencies.html)：各模块之间的调用关系。
- [研究执行序列](../../../outputs/research-web-architecture/03-research-sequence.html)：从请求到任务与交付。
- [数据、文件与证据](../../../outputs/research-web-architecture/04-data-file-flow.html)：来源、冻结和原件交接。
- [能力选择与执行](../../../outputs/research-web-architecture/05-capability-flow.html)：方法、工具及执行流程。
- [任务状态](../../../outputs/research-web-architecture/06-run-state.html)：等待、运行、完成与失败的区分。
- [报告生产](../../../outputs/research-web-architecture/09-report-workflow-sequence.html)：报告 Workflow 的执行路径。
- [入站 MCP 数据流](../../../outputs/research-web-architecture/15-inbound-mcp.html)：客户端、账号、授权与只读材料。

## 接口与源码定位

[接口与源码索引（原 API Atlas）](../../../outputs/research-web-architecture/api-atlas.html) 保留源码声明与实现位置，适合定位模块；
接口怎么调用则查 [API 参考手册](../../../outputs/research-web-architecture/reference-api.html)。

## 保留的设计资料

[完整架构阅读页](../../../outputs/research-web-architecture/architecture.html) 保留旧图册分组、模块清单和原有锚点。
旧 index.html 的架构章节链接会转到该页相应章节；已有图页地址保持。

## 设计限制

一张图说明职责与流程，不证明某个来源已经配置、某个模型已执行或历史数据具有 PIT 资格。
这些问题应回到对应指南、来源元数据和实际结果中判断。
