## 安装前确认

本页提供 macOS 的现有安装入口。确认来源、模型和文件工具所需的账号与权限；具体平台能力以当前安装说明为准。

## 使用现有安装器

在 RWB 仓库根目录执行：

```bash
./setup-web.sh --runtime native
```

需要 Docker 部署时使用安装器已有的 runtime 选项，而不是为文档另装一套服务。
安装完成后按安装器输出的命令打开主界面并运行 Doctor 检查。

## 配置顺序

1. 访问实例并登录，确认当前账号。
2. 按需配置模型；模型可选和本次调用成功分别确认。
3. 配置需要的数据来源，查看依赖、权限、探测和范围限制。
4. 外部客户端按 [MCP 指南](../../../outputs/research-web-architecture/guide-mcp.html) 完成应用登记与授权。
5. 先完成一个小任务，再启用持续跟踪或自动化。

凭据只在本机设置或操作系统凭据库处理，不粘贴到文档、示例、聊天或日志中。

## 日常检查

服务健康不等于某项来源有数据；来源可调用不等于本次研究已经完成；任务结束不等于文件或质量门已经通过。
出现问题时先查看具体错误与查询状态，不随意停止其他用户或任务。

## 相关内容

- [常见问题](../../../outputs/research-web-architecture/troubleshooting.html)
- [数据来源状态](../../../outputs/research-web-architecture/reference-data.html)
- [运行结构与部署](../../../outputs/research-web-architecture/01-deployment.html)
