# 设计资料接入与PyTorch参考

用户指出七域/12候选工具未在文档中心出现，本轮新增独立设计页读取指定8765讨论稿的版本化发布快照，
并从首页、架构设计目录、MCP参考和搜索进入；不修改设计源或业务实现，不将源码合并冒充部署。
用户指定reverse-engineer-anything学习PyTorch。REA受控观察与浏览器实机读取确认首页无左树、
正文完整目录及功能状态；API页为当前模块树、签名/参数/返回与右侧锚点。写法与来源见docs/manual/writing-guide.md。
本轮沿原静态生成、认证、有限白名单和CSP实现，不新增Sphinx或其他依赖。
已提交设计源仅13节，实际8765服务来自weknora-datahub-skill-layer-20261124工作树的未提交17节文档；
本次只在docs/manual保存发布快照并注明历史状态，不编辑或归并该窗口的源文件/分支。
源设计长文首次暴露普通编号列表重复n1/n2 ID，已仅对脚注启用这些ID，未改设计正文。
本机36项Python、200项Node、Ruff、完整改动集门禁与生成物一致性通过；两项独立审查无阻塞。
真实隔离reader验证了完整17节目录、候选工具检索直达、主题跨页/刷新/auto、390px目录及961/1024/1100/1200顶栏无溢出。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"原静态文档节点内增加一个固定设计页和阅读布局，单源渲染；业务接口、权限与运行拓扑保持。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只登记既有文档闭包中的固定页面，测试、runner、作业、依赖及超时均不变。","diagrams":[]} -->
