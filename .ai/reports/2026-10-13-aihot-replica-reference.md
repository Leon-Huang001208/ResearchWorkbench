# AIHOT 复刻参考与证据

目标是将用户提供的开源 AIHOT 阅读与事件流程适配为 RWB 的研究情报，保留原完整 Hot Goal，
不是另开独立应用或替换唯一研究引擎。参考源码只读 checkout `652bd6bf4190df0030824dd86a982ea96f5623d5`，
原后端引用 `8e34e05...` 历史保留。代码 MIT，NOTICE 不许可名字/Logo；采用 RWB 品牌，不复制运营数据。

## Design Read

- artifact：工作台内的资讯阅读区；audience：研究使用者；mode：extension。
- visual-language：暖纸面、轻边框、日期轨道与青绿阅读控件；参考上游 app.css/FeedItem/Timeline/HotTopics。
- visual-variance 1，motion-intensity 1，information-density 8，asset-dependence 2，brand-fidelity 9。
- 叙事作用为资料阅读而非营销首屏；近距离桌面/手机；安静、可扫描；控制优先让首屏进入资料。
- 浅色 #faf9f6/#ffffff/#202a30/#176b75，深色 #13191c/#1a2226/#e7eceb/#12ccd8。
- 系统中文字体栈；8px控件、12px卡片、轻边框/轻影；150ms hover且reduced-motion关闭过渡。

用户已明确指定复刻网站与开源代码，采用该既定设计基线直接实现。没有新增框架、CDN或字体依赖。

## 证据到机制

| 证据 | 结论/复现规则 | 可信度及边界 |
| --- | --- | --- |
| apps/web/app/app.css:95+ | 暖白/青绿语义颜色、浅/深主题、轻边框 | 源码已观测；不是原站像素对比 |
| features/feed/Timeline、FeedItem、HotTopics | 日期轨道、卡片/理由、紧凑排名；详情/来源可追溯 | 静态结构已核对；RWB保留自己的事件/判断合同 |
| README:54、NOTICE | 模型榜/重置监控/运营数据未开源；名称Logo不许可 | 不制造那些模块或占用其品牌 |
| REA ev_2bc9806ca92a4a387504e8ca47af32d30494464edcd34f662ed85bf424ce7bd1 | 线上请求返回blocked/567 | 原站视觉未取得；没有绕过拦截 |
| REA ev_3588abf72246d5daa955803972cdd1c4a927ea355c1d12d80da0d6c5d0d162ed | 本地工作台阅读区真实渲染、空/未配置态 | 隔离offline研究客户端，不证明后台运行 |
| REA ev_3a1fd1c7538f4ff5f3b9c07d006655a50aaafdf542ac907dfc0d1a60ebd0146e | 外部总览读取真实Golddata及stale标记，八栏目共用主题 | 不把外部记录当成本地Hot原件 |
| 只读PG→renderHotWorkspace | 原schema暂停时仍可提取真实宏观记录作版式预览 | preview脚本，不是绕过公开入口的产品验收 |
| REA ev_7ab74e0f5a06dcb3e6de841d100726a77f4e0fc33af4b05d4b70b60b107f1186 | 最终桌面1440×1000真实存储事件预览 | 受控Chrome完整截图，page-error零；预览favicon404 |
| REA ev_80127142a94703ab613665fa3ec59e68ad0f930aface1323751f73fc991afd43 | 最终手机390×844紧凑标题/导航/日期与卡片 | 同一只读资料；不是实时采集或正式研究验收 |

最终截图保存于 `/Users/leon/.codex/preview-audits/aihot-replica-20261013/` 的
`rwb-reader-real-desktop-final.png` 与 `rwb-reader-real-mobile-final.png`。首次截图不代表最终样式。
前端全量391 PASS/1 SKIP；Hot/Reader/Intel目标23 PASS，治理与项目边界检查见权威进度。

## 保留的功能及下一步

原导航、八栏目、事件详情/材料版本、来源、纠错、简报、Origin/明确动作边界保持。
新增快捷频道和排序只触发GET；分页仍用固定cutoff，不生成模型调用。异步失败清空旧页，
过期失败不污染新视图。观察时间不是发布时间；本页热度不是完整排行榜，不制造走势。

上游支持精选/全量、热点事件、日报/周月报、文章与事件详情、已读/收藏等。该轮仅落实阅读面板，
完整精选模型、关注/计划简报、正式DSH研究、恢复、连续采集、Docker与候选CI仍按原Goal推进。
权威进度仍为 `2026-10-12-hot-intel-resume-PROGRESS.md`，本页是参考证据，不替代完成验收。
