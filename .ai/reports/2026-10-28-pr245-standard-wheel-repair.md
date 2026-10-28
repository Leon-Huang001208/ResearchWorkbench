# PR245 repair3：沿产品标准 wheel 安装与隔离准入

宿主 macOS；Web CI 窄修复，基线 `181d7e435e8c9108f66159db544d64f205b15330`。
原完整 Web 锁／七项 metadata／optional 失败关闭、唯一 DSH、所有原测试与三 CI／平台门保留。
本轮不安装依赖、不变更锁或产品资源算法，不改 CDN、pin、hash、重试、job、runner 或 timeout。

## 两个原失败分别归因

Checks `40664733092` 原件 controller `logs/pr245-181-ci/checks-40664733092.log:679–719`：
Web 全锁和 dev 工具安装成功，editable 元数据回退到 Hatchling `build_editable_detection`，
显式导入未锁 `editables` 失败。七项metadata、Host／Native前置及Python／JS均未执行。
这与此前 jsonpointer 污染不同，不能以升级锁、装 editables 或跳过准入处理。

Mac `40664733223` 原件 controller `logs/pr245-181-ci/mac-40664733223.log:523–530`：
固定DSH的官方SheetJS tarball两轮fetch TimeoutError（DOM error23），最终
`dsh_build_step_1_failed`。本候选 health／Doctor／SDK均NOT_RUN。
这是独立外部下载失败，不修改 CDN／pin／hash／retry 或预算；后继原Mac门自然重建，旧绿不复用。

## 先离线证明，再采用既有产品合同

`scripts/setup_web.py:577` 原生产安装使用普通非editable项目 wheel、`--no-build-isolation`
与`--no-deps`。现有Hatchling实际 `get_requires_for_build_wheel()` 为 `[]`，
`get_requires_for_build_editable()` 为 `['editables~=0.3']`，现release环境没有editables。

预登记外部opaque根、磁盘门和owner后，在Seatbelt `deny network*`、PIP_NO_INDEX=1下：

- 真实 `python -B -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir OWNED PROJECT`
  成功，1.841秒，没有安装wheel。
- `python -I -S -B` 只开放现Web锁六项build依赖，实际未锁editables导入被拒绝后，
  标准wheel仍成功，1.423秒；六项实装版本逐项等于web.lock。
- 两wheel同SHA256 `6d5e4a016a3326531d5bef46494af30c05ca3fa2dd2d5974690846c0b3ee709e`，
  38,085,817字节，2655项；2651项目文件逐字节等于checkout，无editable／.pth产物。
- archive metadata读取可见distribution、RECORD、rwb入口，入口load callable与包归属可解析。
  这只是archive检查，不能认证实际安装、生成console script或真实Host运行。

证据 controller `logs/pr245-wheel-probe/`；两原wheel及脚本归档SHA256
`9953cc10bbdc00654320539355c195a6a047cf2f717ed65c18339480f7b1a4ad`，实际恢复内容相等后精确回收。

## 独立的真实 wheel-only Host／Catalog／Native 证明

另外预登记opaque根，仅解包同一wheel，不安装、不复制requirements／scripts，不加入checkout。
fresh `-I` child保留真实受管解释器／前缀供锁定第三方依赖验证；自定义finder只允许项目模块
来自解包wheel，第三方模块来自与现Web锁匹配的已有分发白名单。Seatbelt禁网，并拒绝读取
checkout、release源码／requirements／scripts／resources／runtimes／vendor原件；site中
已装项目包只允许metadata stat供distribution inventory使用，源文件data读取仍拒绝。
另对实际存在的四个fallback文件open，全部得到PermissionError。

真实 `runtime_identity()` 得到v3／七依赖，九包manifest逐件通过、三方法构造成功，
`load_runtime_contract()` 从解包wheel的runtimes JSON读到固定DSH pin；全部83个项目模块
origin均在wheel解包根。真实 `CapabilityCatalog` fixture创建56项，3.729秒，未启动Host daemon。
fresh Native仅从该wheel helper安装原guard后实际导入jsonschema并校验idn-hostname成功，
app／core不加载。这才是独立的真实调用证据，不能与前面的archive入口检查混称。

`whole_lock_present=false`：pack_dependencies原有230–233行明确区分源码whole-lock核验与
已安装wheel包内投影合同，并非从release补齐文件。现有
`test_pack_runtime_identity.py::test_actual_wheel_contains_lock_and_builds_packs_without_a_checkout`
及`test_runtime_contract.py:441`也覆盖wheel提取／`-I -S`包内runtimes路径。
其他isolated测试显式提供其checkout／受管script绝对路径；不依赖editable隐式可见性。
本轮无需增加产品资源stage、force-include、手工.pth或改变投影算法。

证据 controller `logs/pr245-wheel-resource-probe/{summary.json,child-real-catalog-no-source-data.log,native-wheel-only.log,deny-fallback-existing.log}`。
探针早期stdlib动态名字、absent查找及只读metadata stat限制的诊断失败均保留，没有修改产品策略。

## 最小diff与本地验证

Checks只改两条命令：根包采用 `pip install --no-index --no-deps --no-build-isolation .`；
PY_ADMISSION采用`-I -B`，实际验证已安装包而非当前目录源码。原声明解析、哈希、七metadata、
Host／Native拒绝与完整测试清单保持。治理仍为纯stdlib；新增真实离线wheel构建和wheel-only
九包／三方法资源回归只放既有Web JS通配符，不向Project Constraints引入Hatchling。

固定Node24.19／原release Python和DSH路径，执行两近测试文件：24 passed、0skip，4.006秒；
其中真实标准wheel构建／资源回归2.801秒。完整日志及本组owned归档恢复回执在
controller `logs/pr245-optional-import-repair/repair3-focused.{log,json}`。
同一治理文件在实际 Python `-I -S` 包装器下22 passed、0skip，1.173秒，证明轻量门
不依赖site-packages；见`repair3-portable-stdlib.{log,json}`。Project Constraints、
文档治理、研究架构、Python索引和diff-check全部通过，YAML／所有shell `bash -n`／
三个实际Python heredoc AST均通过，见`repair3-integrity.json`。根README用户入口、
配置与功能未变，不需要改写；结构决定保持原验收拓扑。
尚未在本机pip install，不能将这些结果称为新CI实际安装／console script或完整Python闭包通过。
后续独立SPEC／quality、完整闭包与新候选原三CI由controller执行；未执行保持NOT_RUN。

## 临时资源与恢复证据

真实Catalog产生只读版本目录，首次删除明确失败并保留blocked回执，未把部分清理称为cleaned。
经controller仅针对本组两树的窄授权，逐项验证UID／非链接／inode及manifest后仅补目录owner-write
并精确删除，逐路径原模式、目标和结果均记录。先前tar data filter恢复只证明内容相等，
不能认证原mode完全恢复；该历史限制和诊断回执保留，不补改为旧模式PASS。

随后按新增窄授权重新独立恢复同archive：4010路径逐fd恢复archive原安全mode，独立全量重验
bytes／type／no-links／UID／mode全部一致后才回收。清理中目录nlink按本组已删直接条目账本
校验（本机APFS实测删除直接文件也使父目录nlink下降），文件nlink必须1，剩余路径拒绝新增未知项。
最终无剩余根，见`exact-mode-recovery.json`与`exact-mode-cleanup-final.json`。
archive SHA256 `9805926785d4f2ab95fb276a999ed6b9b8c8906fba30bf1381a75a387339806c`保留；
没有改变source checkout、系统、服务、其他任务树或任何业务资源权限。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只将原Checks项目安装恢复为产品既有普通wheel路径并隔离已安装包准入，原job、runner、预算、锁、DSH与平台验收拓扑保持；真实构建回归进入既有Web通配符，轻量Constraints不增加产品依赖。","diagrams":[]} -->
