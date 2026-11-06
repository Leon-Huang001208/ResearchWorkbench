# WeKnora 研究资料底座接入

- Host: macOS / Mac mini；Task kind: feature development。
- 本平台范围：隔离源码、离线权限/引用/截止期回归、适用 Mac CI；其他平台 NOT_RUN。
- 基线：46d86544097a04f2404fe0599f90d3553dc0c028。
- 目标：研究资料由 WeKnora 管理；RWB 提供账号隔离的检索/读取与独立证据冻结。
- 边界：不停止既有服务，不处理实际凭据，不安装依赖，不迁移生产资料，不触发模型或报告任务。
- 首期：固定协议、候选容量/盘点/对照工具、认证接口、不可变证据与诊断。
- 并行报告：原 WorkBuddy/Wind 周报任务独立；未收到冻结材料与交接，不重跑成稿。
- 验收层次：源码验证、真实服务、真实宿主、报告业务、部署、资源收尾分别记录。
- 当前：in_progress；部署/真实语料对照/模型调用/业务报告均 NOT_RUN。

## 2026-11-06 实施检查点

- 已新增 knowledge_backend：用户 JWT / 当前 workspace、受限检索、原件读取、用户确认资料范围、独立冻结写入与冷 Doctor。
- 报告范围同时绑定原件 SHA256 与解析分块身份/正文/定位指纹；不把上游 MD5 当原件 SHA256。
- 独立评审发现并修复：UI 空间ID数字/字符串不一致、manifest超限后提交、原始origin泄漏、分块编辑穿透、业务总体超时。
- WIP验证：client+patch 18 PASS；service+integrity 19 PASS；API+扩展integrity 12 PASS；candidate 15 PASS；Node界面组合25 PASS。集合有重叠，不能相加为唯一用例数，尚非最终exact-SHA验收。
- pytest失败回执保持，修复后复用原root/nonce/用例集合生成新proof，成功经原retire入口回收。
- 一次临时根因Darwin UF_TRACKED/UF_HIDDEN属性拒绝准入：仅对本任务nonce匹配、无占用的合成文件复查inode/sha后修复属性，完整清单在logs/weknora-integrity-attribute-recovery.json；未改原失败回执内容或放松检查器。
- 用户已另行授权隔离准备 Go1.26工具链与固定源码Go模块用于构建测试，未授权部署或迁移。
- Go1.26.10 darwin/arm64官方archive SHA256校验通过，根/private/tmp/rwb-weknora-build-7b49e831；固定源码archive校验记录在logs/weknora-go-source.json。
- 0001仅尊重显式单文档摘要opt-out；0002 retrieval-only专用实例强制策略已生成，仍须实际Go测试，当前不宣称零LLM UI验收。
- 剩余：最终review/精确候选验证、架构图与文档、CI、上游Go编译测试、隔离浏览器。真实WeKnora服务、云Embedding、周报金标对照、原窗口交接、生产部署/迁移继续NOT_RUN。
