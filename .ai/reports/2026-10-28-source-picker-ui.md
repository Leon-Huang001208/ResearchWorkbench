# C6b：研究组合包已保存原文选材 UI

- 日期／宿主：2026-10-28，macOS Mac mini，Web 功能开发。
- 任务：`seek-packs-20261027-7bda5752`；复用已开始的 Harness，不另建任务或重复 Git 完整性检查。
- 基线：C6a 首次未创建证明补丁 `77fe79a008eb8be55d09e70742d63ccb3264f1b1`。
- 范围：原抽屉、3个API薄调用、JS回归、真实临时Host／Chrome离线夹具和本模块文档；不改生产Python、SourceProof／Store／Native／Sender／schema／旧八合同。
- 整体状态：C6b 本地候选；不冒领 T3／62 Skill／78 Tool／C3C4／T4T5 完成。独立SPEC／TSQUALITY与测试Python品质审由主控进行。

## 实现与受保护合同

`core.mjs` 增加安全列表、只读预览和显式冻结薄调用；只有 `/handoffs` 与 `/source-selections/freeze` 的4xx明确携带 `handoff_outcome=not_created` 才读取未创建证明。不根据普通403／409／404推断。

`scenarios.mjs` 在调研前置、海内外舆情增加明确原文模式。本人会话列表和source metadata分开读取；SID＋source ID作为复合键，跨会话相同ID不合并。快照勾选保留但原文请求的 dataset_ids／material_ids为空，不将web ID塞入快照、不复制正文为上传。第一份所选来源会话已有三scope才准许调用preview；不自动开scope／抓源。观察或既有资料合同锁定入口保持原路径。

列表仅投影safe metadata；日级日期、精确未知时刻、Host捕获核验、上游完整性与语言／地域／角色／历史PIT分别说明。跨会话选择、问题、方法参数在读取失败、410、来源变化时保留；消失的已选原文继续显示不可用并可明确取消。空会话提示与其他会话已选项并列，避免将空列表误当读取失败。

新preview消费真实 `qualification`，保留缺口／partial与算法1.1.0；freeze绑定完整原请求、digest及唯一key，成功才开放原草稿导航。首次未创建证明恢复编辑并使预览失效；真实Native未知、已prepared旧selection、文件发布未知或丢响应继续持原key/body查询。原Send独立，准备不发送模型。

沿用原620px抽屉、主题token、控件层级和App滚动／number节点／selection恢复；不新增门户或sender。原结果safeDTO、文件／研究质量、基金／主题／legacyClaw、stock锁定保持。

## 实际验证

- RED：新增source-picker 3测试初跑全部因缺少 `selectSourceSession` 失败；实现后与旧目标测试27通过；扩展后目标29通过，最终新增第6测试进入全量。
- 最终 Node24 JS：`node --test tests/javascript/research_web*.test.mjs`，使用实际 `RWB_TEST_PYTHON` 与固定DSH双环境变量；**1244通过、0失败、0跳过**，10451.24ms。日志：`/Users/leon/.codex/evidence/seek-packs-20261027-7bda5752/c6b-regression-b6e18bfe/javascript-all-final-dsh.log`。
- 旧 `research_web_scenarios_real_backend.mjs` 原脚本全部断言：4 checks PASS；仍包含两宽度准备／资产工作区、导入摘要比较与关系、legacy、search Enter／route race零创建、裸代码拒绝与修正。仅外部runner副本改输出路径，仓库脚本未改。
- B2补充：`research_web_packs_real_backend.mjs` 20 checks PASS；`research_web_packs_scroll_real_backend.mjs` 4 checks PASS。分别归档于同一regression证据根的 `packs/`、`packs_scroll/`、`scenarios/`，不与新旅程混算。
- 新source首个完整成功run：`c6b-625f210b`，9 checks PASS；两宽度×三主体、深浅主题、跨会话、长标题／长文本、模式切换、preview零创建、丢响应后lookup、单草稿zero messages、显式原Send（仅离线Native夹具）、来源变化409证明保输入、410。
- 最终source增补run：`c6b-final-2f804995`，**10 checks PASS**。除原9项范围，分别增加真正服务端Native创建未知（首次HTTP错误无未创建证明，原lookup返回unknown，刷新仍只查询，Native创建尝试1、自动重试0）和两宽度fresh请求在freeze前撤权403的证明／保输入修正。与首个9项run独立计数。
- Python测试夹具：Black check、Ruff 0.16.10、isort check均PASS；Ruff使用已有uv缓存二进制，无安装。未改生产Python，未重跑C6a全47／真实Native两包。
- `git diff --check` PASS。源码未运行真实LLM／供应商、public fetch、正式DB或用户浏览器；mypy／CI／Mac干净安装／常驻部署／Windows／Linux为NOT_RUN。

## 失败与修正记录

1. 首个source run `c6b-a831dc22`：三主体preview通过后，空会话提示被其他会话已选项遮蔽；已修为独立当前会话空态。其cleanup首次遇到fixture只读skill目录EACCES；准确登记root下恢复目录owner写权限后完成清理，后续runner内置同一受限动作。失败日志和截图保留。
2. JS全集首跑缺 `RWB_TEST_PYTHON`，3项环境失败；设定解释器后1240通过／3条件跳过。按主控要求补固定DSH双变量后最终1244全部通过，不修改skip门。
3. 旧旅程外部Python启动器首次未处理 `-u`，启动前失败；启动器修正后原4 checks通过，未改变业务断言。启动器及resource登记留在regression证据根。
4. `c6b-final-396ba051` 第二宽度403没有not_created：与第一宽度已prepared使用了完全相同请求，原不可变selection已存在，后端保守拒绝证明正确；UI未猜测解锁。改为每宽度独立合法subject后重验，未改后端。
5. `c6b-final-d37c2ad9` 两宽度fresh 403纠正已通过；fixture误以为Native创建失败首次HTTP错误直接带unknown DTO而失败。读取原后端合同后改为“首次错误无证明→显式原lookup为unknown”，最终10项run通过；没有修改生产合同。

## 证据与收尾

所有来源均为明确冻结／合成fixture，经真实stdlib HTTPResponse、同进程reader和socket／HTTP guard；浏览器只允许本机origin，离线Native fixture不等于真实模型质量。

新runner在启动前登记task／UID／PID／dev／inode，登记Host与Chrome进程；关闭自己持有的browser／child后核精确scratch身份，仅恢复自有临时只读目录的owner写权限，再删除。外部截图／日志／result按逐文件SHA-256读回。旧回归的独立scratch在进程清单确认无占用、46个证据文件hash读回后回收150827705字节；`c6b-regression-b6e18bfe/cleanup.json`与每个source run的cleanup.json保留。旧资源、其他worktree／缓存／Docker／常驻不清理。候选提交由主控按固定SHA独立评审。

ROOT_PENDING：全changed-set Router、API Atlas、七文档／图聚合、独立评审、CI、最终交付与部署由主控维护；本报告不替代这些门。
