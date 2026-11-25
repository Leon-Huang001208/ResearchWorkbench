## 要完成什么

从外部 MCP 客户端发现 RWB 工具，完成一次获准材料的只读发现。此样板不取新数据、不执行 Skill 或模型。

## 前置条件

- RWB 管理员已经启用入站 MCP；客户端能访问实例的私网 HTTPS 地址。
- 客户端已按该实例的应用登记完成 OAuth/PKCE，并获 rwb.read 授权。
- 要读取原件，还需要明确批准的材料与可用后端。只有连接成功并不足以取得所有资料。

## 连接步骤

1. 在支持远程 MCP 的客户端填写你自己的 RWB 规范地址，路径为 /mcp。
2. 使用该实例登记的应用身份完成登录；不要把浏览器 Cookie 或厂商密钥当作 MCP 凭据。
3. 在同意页核对账号、应用与权限；先发现工具，再调用当前令牌实际能看到的工具。
4. 阅读或撤销授权可回到 RWB 的已授权应用入口。

## 最小工具调用

下面是客户端的工具调用对象，**不是直接发送到 HTTP 接口的完整协议报文**。认证和 MCP 初始化由客户端处理。

```json
{
  "name": "rwb_capabilities_list",
  "arguments": {}
}
```

## 预期结果

工具返回当前授权可见的能力元数据：scope 为 rwb.read，execution 为 false，并列出 contexts。没有获准材料时 contexts 可以为空。

只取一个返回的 context_id，再查看该范围内的数据集：

```json
{
  "name": "rwb_datasets_list",
  "arguments": {
    "context_id": "<替换为本次返回的 context_id>"
  }
}
```

预期结果包含 context_id 和 items。不要使用别的账号或上次授权的上下文标识，也不要把空列表解释为整个平台没有数据。

从 items 中选择一条获准数据集，将它的 object_id 作为 dataset_id，再读取少量冻结行：

```json
{
  "name": "rwb_dataset_read",
  "arguments": {
    "context_id": "<替换为该条材料的 context_id>",
    "dataset_id": "<替换为该条材料的 object_id>",
    "view": "rows",
    "offset": 0,
    "limit": 10
  }
}
```

预期结果中 items 是本页数据，total 表示冻结结果总量，partial 表示本次响应未覆盖完整结果，不能直接当作是否还有下一页；同时保留原件与行文件的校验信息。
读取的是已冻结结果，不调用供应商取新数据。items 为空时，先判断是否本来没有数据或已到分页末尾。

## 常见错误

- 未认证、scope 不足：在客户端重新完成正确的授权，不用 Cookie 或代理绕过。
- 工具不存在：以当前 tools/list 为准；rwb.read 不会自动获得取数工具。
- 后端未就绪、维护中或忙碌：按原错误处理；不能通过发现工具冷启动任意研究环境。
- 原件校验失败：停止使用该结果，核对原件与来源，不用部分内容绕过校验。
- 返回过大：缩小受支持的分页范围，保留分页和截断信息。

## 相关参考

- [MCP 角色与工具参考](../../../outputs/research-web-architecture/reference-mcp.html)
- [入站 MCP 的授权数据流](../../../outputs/research-web-architecture/15-inbound-mcp.html)
- [数据目录与结果语义](../../../outputs/research-web-architecture/reference-data.html)
