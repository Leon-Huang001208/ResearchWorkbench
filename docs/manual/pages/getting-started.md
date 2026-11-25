RWB 把研究任务、数据与资料、执行方法和交付文件放在同一个工作台。先完成一个小任务，再扩展研究范围。

## 要完成什么

找到当前账号能使用的数据和技能，知道一次研究怎样留下来源与文件。第一次使用不需要先读架构图。

## 前置条件

- 能访问你的 RWB 地址，并已登录正确的账号。
- 查询新数据需要对应来源已配置、依赖就绪且账号有权限。
- 执行研究需要可用的模型与运行环境；读取目录不等于执行研究。

## 最短路径

1. 从主界面确认账号和运行状态。
2. 阅读[数据使用指南](../../../outputs/research-web-architecture/guide-data.html)，先核对来源是否可调用。
3. 阅读[技能使用指南](../../../outputs/research-web-architecture/guide-skills.html)，选择与任务匹配的技能和版本。
4. 在研究会话中明确对象、时间范围、资料和预期输出；确认需要的调用后执行。
5. 完成后检查本次来源、数据时点、缺失项和文件，而不是只看任务是否结束。

外部客户端用户从 [MCP 接入指南](../../../outputs/research-web-architecture/guide-mcp.html) 开始；开发者可直接查 [API 参考](../../../outputs/research-web-architecture/reference-api.html)。

## 一个小任务示例

在研究会话中明确提出：

> 请只使用我已提供的这份资料，概括主要观点、证据和不能确认的地方；先在聊天里回答，不生成文件，也不额外取数。

选择能处理该材料的技能，并核对其输入要求。没有提供资料时，应先补材料，而不是把缺失内容当成事实。

## 预期结果

你应能辨别回答依据了哪些资料、哪些结论仍未知。技能没有声明文件输出或当前环境没有文件工具时，不应把聊天文本当作已生成的 DOCX/XLSX。

## 常见问题

- 无法打开文档或会话过期：回主界面登录，见[登录与文档访问](../../../outputs/research-web-architecture/troubleshooting.html#登录与文档访问)。
- 来源存在但不可调用：先查状态和限制，不能仅凭目录条目判断连通。
- 需要代码调用：从具体业务域查接口，不能直接执行本文档页面中的网络请求。

## 接下来

- [数据：目录、权限和快照](../../../outputs/research-web-architecture/guide-data.html)
- [Skill：方法、输入和输出](../../../outputs/research-web-architecture/guide-skills.html)
- [MCP：外部接入和授权](../../../outputs/research-web-architecture/guide-mcp.html)
