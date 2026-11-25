# 文档阅读布局与主题

宿主macOS，文档展示修复；业务接口、数据、依赖与账号权限保持。
实机已复现：隔离CSP的页面选择dark后，跨页回到auto和白底。
首屏主题与URL偏好同步，站内链接/搜索结果保留偏好，auto跟随系统，显式选择不被系统覆盖。
布局参考Python/PyTorch文档，左侧搜索/分组目录，中间正文、右侧本页目录；收紧段落间距并去除章节横线。
Browser plugin未提供对应browser skill，使用已有Playwright验证；不新增依赖。
在原opaque sandbox/CSP下验证了显式浅/深色覆盖、auto系统变化、跨页/刷新/返回、搜索结果query/hash、
390px CtrlK目录及无整页溢出。评审发现旧架构/Atlas主题桥接遗漏，已补齐两套旧脚本及图页固定导航；
浏览器确认暗色Atlas接收参数，图页手动切浅色后返回首页保持light。
35项Python、162项Node及Ruff通过；图页已有内嵌字体被原CSP阻止的日志未放宽策略，正文阅读器无pageerror。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"只调整原静态阅读模板、CSS和主题交互；文档白名单、CSP、认证、运行拓扑和业务调用不变。","diagrams":[]} -->
