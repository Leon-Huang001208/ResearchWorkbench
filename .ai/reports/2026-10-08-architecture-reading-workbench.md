# 架构阅读工作台

宿主macOS，任务类型功能开发，taskId task-20261008-arch-reading-25f8210a7120；基线b0ed27b75aa915346f6cf1f1db984623dfe25f14。用户已确认设计系统与v0的阅读工作台方向。

## 边界与设计

沿用原五层阅读结构、11个图入口与20个模块；全部数量继续由清单派生，不作常量验收。保持路由、图源、.card、#top/#module-*及全部说明/源码/测试/API链接。侧栏固定、首屏总览铺开、模块渐进展开；当前真实logo与已批准主产品字体/颜色保持。v0中的Tweaks与图缩略占位不进入正式产品，正式页面提供主题与阅读密度控制。

搜索、空状态、清除、快捷键、源路径匹配及hash源码展开只有页内行为。opaque CSP不变，主题不访问localStorage，不引入网络依赖、模型调用或资源读取入口。Node状态测试使用受限DOM契约验证行为，不冒充浏览器像素验收。

## 实际进展

- 新界面/派生搜索/真实PNG输入三组测试先RED；交互状态测试也先RED，再实现GREEN。
- 当前架构Node合同80/80 PASS，完整选中Node合同108/108 PASS，生成与--check、文档分类、Python索引与完整7路径Project Constraints均PASS。
- 独立TypeScript/JavaScript审查发现窄屏布局漏接、同节其他条目可见时hash源码详情未揭示父模块两项P2；均补复现测试RED后修复GREEN，复核无剩余阻塞。远端交付仍待CI与合并。
- 未请求新的可执行浏览器验收，不把v0人工确认或Node状态测试写成正式浏览器验收PASS。图源/Archify HTML不变，原哈希视觉证据继续复用。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"重排清单派生首页并增加页内阅读控件，清单、图文导航、说明/API/源码/测试关系保持；没有变更图源或文档路由及安全拓扑。","diagrams":[]} -->

## 源码与生成物身份

被说明源码快照 `a8c71603287fe8da3d1d5b566704f25628de8106` 包含正式生成器、合同测试和说明；清单仓库链接与派生页面绑定此快照。图源/Archify HTML及人工审阅哈希未变。最终生成物/交付提交另记，不要求产物内嵌包含自身的SHA。
