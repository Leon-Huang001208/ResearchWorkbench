# PR245 Catalog metadata 热路径修复

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"Catalog仅在可证明stock的metadata API／finder／PathDistribution边界内收窄静态依赖扫描；能力版本、发布、原生发现、权限及唯一DSH边界不变。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"既有双worker调度和stager只增加缺final时的节流lower-bound安全进度；合法final权威性、JUnit、exact-union、job、runner、worker和timeout合同不变。","diagrams":[]} -->

## 范围

- 宿主：macOS，功能开发与本机定点验证。
- 目标：缩短 Research Web Checks 中真实能力目录构造的 metadata 热路径。
- 非目标：不减少测试、publish/save/runtime freshness、权限/身份门，不修改 CI runner、worker 数、
  timeout、依赖、固定 DSH、常驻服务或其他平台状态。

## 诊断与实现

冻结前本机单例 `cProfile` 为 9.518 秒；`CapabilityCatalog.validate` 108 次累计 4.893 秒，
`importlib.metadata.packages_distributions` 12 次累计 3.518 秒，并为无关记录构造/存在性检查
150,422 个 `PackagePath`。

修复保留初始化事务的一次完整清单。非初始化验证先核公共API、Distribution discover／resolver、
默认PathFinder函数与descriptor、其动态导入的MetadataPathFinder类／find descriptor、
PathDistribution类、Distribution.files/readers、PackagePath／FileHash及top-level helper完整闭包；
所有参与证明的class member均先以`inspect.getattr_static`核raw descriptor身份，只有身份已知后才提取
函数做指纹，不在fallback选择前普通绑定未知descriptor；
每个实际参与的命名Python function／property／classmethod同时绑定function、immutable code、
defaults／kwdefaults及closure cell identity，不信任`__module__`自报。任何真实custom finder／内部
动态委托替换或原地`__code__`替换在枚举前回原API并只消费一次；必需私有primitive以sentinel安全
捕获，缺失时Catalog仍可导入并走公共API。可证明stock时只对本次
`external_modules`建fresh投影；枚举若返回未知Distribution类型，或前后闭包身份变化，则固定
`dependency_inventory_changed`失败关闭且不二次枚举：

- `top_level.txt` 声明直接匹配；
- 无声明时沿stdlib的RECORD／installed-files／SOURCES选择，逐行复现PackagePath、FileHash、size及
  arity构造错误，只对候选top-level路径做存在性检查；
- namespace 多发行包、缺失文件、下一次 metadata/路径变化及异常不缓存；
- 独立评审发现不相关发行包的损坏 `METADATA` 会被投影跳过；修复后，声明式包始终读取
  `Name`，推断式包在无指定模块命中时也读取 `Name`，仅当读取失败时检查不相关文件是否实际
  存在，以保持公共 API 的异常传播，同时正常路径仍不对不相关 RECORD 文件做 stat。
  新增声明、推断和缺失推断文件三例同旧公共 API 对照；最终候选分批运行 Catalog 51 例通过。
- unsupported primitive或custom finder回退原`packages_distributions()`。

没有缓存 dependency/permission/identity/PASS/policy，也没有改变检查和 issue 顺序。
固定构造的真实计数保持 6 次 runtime、12 次 policy build、18 次 module inventory、56 次 check、
56 次 publish 和 281 次 save；profile 的 `CapabilityCatalog.validate=108` 是实际调用计数，不把它
误写或弱化成 56。

## 实际证据

- TDD RED：新增两项投影测试在产品修改前以
  `TypeError: _installed_module_distributions() takes 1 positional argument but 2 were given`
  失败。
- Fresh SPEC `logs/pr245-final-freeze-20261030/spec-review.md`（SHA-256
  `aa86a2149bffb6db0f4d063fd60d5059999fec0335905d2ab6e5aaac95dc1585`）拒绝epoch1的3个P1／1个P2；
  原15-source manifest、profile、53-body历史raw均保留，没有覆盖或改写。
- epoch2 Python QUALITY `logs/pr245-final-freeze-20261030-epoch2/quality-review.md`（SHA-256
  `0ec3e67730f48dbf67f0c09c924828bcf8499d31888786ad85740d4bd1258b9f`）指出默认PathFinder动态委托
  未完全绑定；epoch2 source/raw/SPEC/QA均保留。
- Root epoch3预读进一步指出unknown `_discover_resolvers`会先执行及same-function `__code__`替换逃口；
  新TDD分别复现stateful helper被调用两次、public API/inferred helper原地code替换假missing，以及缺
  private reader导致模块导入失败。
- epoch5 Fresh SPEC `logs/pr245-final-freeze-20261030-epoch5/spec-review.md`（SHA-256
  `93b79934f70836ca48c80167bbc2b87e74dbd10e40e67893cb0b0d2d11c6a24e`）指出普通class access仍可执行
  stateful descriptor并绕过公共API错误；两项新RED分别固定PathFinder descriptor只能由公共fallback
  调用一次，以及非目标PackagePath.locate错误必须传播。RED raw SHA-256为
  `9482a399243ca46245e261beb8607520ee7cbdea35ffaaa1eddcbb3bd6fd9a18`，修复后二项GREEN raw SHA-256为
  `4dca0d3e1b7e634c385dffb2efff8f11aa482960f4a45ae5973da6a11e561e39`。
- 最终metadata与ordered-oracle按真实collect拆为12／12两个packet，共24 passed（8.72秒／7.07秒）；
  含初始化fresh、
  real temp dist-info／egg-info、重复namespace、missing path、
  RECORD更新、非目标行invalid size／extra arity、真实sys.meta_path custom finder单次调用、公共API
  monkeypatch、MetadataPathFinder类替换、同类find descriptor替换、PathDistribution hide／expose／
  exception、stateful PathFinder／PackagePath descriptor、post-projection闭包变化、stateful resolver
  single-fallback、public/helper原地code替换、
  missing-private-primitive隔离import、真实环境等价及异常传播。collect/node/raw位于
  `logs/pr245-metadata-packets-20261030-epoch6/`，collect SHA-256
  `00b875caaa3f5abfd0e4699fb4b0745529cf2dbca5b5eb0b8f1e1ead44d70068`。
- 完整静态descriptor、委托、code/defaults闭包及sentinel兼容证明后的最终字节固定oracle：
  1 passed/6.83秒；cProfile总计7.016秒。最终profile为
  `logs/pr245-catalog-projection-20261030-epoch7/final.prof`（SHA-256
  `09250f7acc14393b836310592f7699eee0f9508efc87b583ba3415846ec4def5`），原始输出同目录`final.log`
  （SHA-256 `d816134d7423f3d1994b1d12397a91cb8fafb4d996a29062eb03c7d1b7391f9c`）。
- 最终profile中完整`packages_distributions`仍为1次/0.305秒，11次fresh投影合计0.737秒，
  `validate=108`累计2.394秒。相对冻结9.518秒同样本减少约26.3%；epoch2严格profile 6.761秒及其他
  中间epoch均保留但不冒充最终字节性能；不保证Linux／CI提速。
- 上述 profile 属于修复不相关 `METADATA` 错误前的 epoch7 字节；本次修复后的耗时尚未重测，
  不能将 26.3% 作为新候选的性能验收结论。
- `git diff --check`：PASS。

## 缺 final 的安全 worker 诊断

原分区执行器增加私有同目录`progress.json`。hook只更新内存中唯一assigned node、最坏outcome及
单次teardown完成；持久化限startup、collection、首次执行阶段及其后最多每5秒，是事件驱动的
last-persisted lower-bound，`elapsedSeconds`只标记该次落盘相对worker启动的时间。5秒只限制写入频率；
没有新hook事件或单次调用较长时可任意更旧，绝不表示当前或最终结果。普通诊断状态／写盘异常只置固定
disabled/error code，不记录正文、不改变原pytest
pass/fail/skip；BaseException不由诊断层吞掉，critical final路径不执行最终progress flush。

stager仅当`result.json`缺失时解析并严格核owner、闭合schema、类型、plan、node白名单和边界；合法
final存在时完全不读取progress JSON语义，即使progress恶意／损坏也不改写final/JUnit/exact-union。
缺final时progress仍不能生成final、替代JUnit或把scheduler/worker提升为PASS。

- epoch1 TDD RED保留：真实双worker／SIGTERM缺progress，缺final不输出诊断且接受未知字段，共4项。
- Fresh SPEC TDD RED新增：真实pytest9 subtest使计数越界；合法final被malformed progress拒绝；startup／
  collection／setup／call／teardown OSError改变verdict；custom finder遗漏；非目标RECORD坏size／arity被吞。
  修复后相关13个progress定点及最终20个metadata合同body加2个ordered-oracle body通过。
- 首次快速诊断曾以单进程运行53 body并通过（3.05秒），但它不满足每进程最多20 body，故不作为
  合规最终证据，也未覆盖或删除。
- 修复后真实`--collect-only`为66个完整nodeID，按原顺序切为17／17／16／16（每进程≤20），分别
  17 passed/1.07秒、17 passed/0.89秒、16 passed/1.39秒、16 passed/0.96秒。精确nodeID/raw位于
  `logs/pr245-safe-progress-packets-20261030-epoch6/`；collect SHA-256
  `847b0b481c27527c22e65dc5b32901302f2be12b03c65eb37d7964d083ac6e57`，四packet node清单为
  `0837b238fd6feba35c0fc3322993634d6bdfca8254d852b6037b95f340f6204a`、
  `10ae7a50ec2f49bb181adb1ca39c0b977007dca8768febaac224a25a1a4d894f`、
  `15742d2d60a71ff4e7f08557f01bbe998bcfff09c8629982243bcc82e76c0dca`、
  `f518eee147a540cf1ce5fd32af5fdead7ec8f1c592438d4575587592d6268415`；顺序拼接与collect前66行一致。
- 首次epoch6执行未带仓库根`PYTHONPATH`，子进程`-P`无法导入`scripts`，四包均为真实失败；原
  `packet-*.raw.log`和仅第一包产生的`retry1`失败raw均保留。补齐既有固定运行环境后的合规结果记录在
  `packet-*.retry2.raw.log`，未借此修改测试或产品语义。
- 覆盖真实pytest9 unittest subTest pass／skip／fail、真实SIGTERM、原pass／fail／skip、五阶段OSError、
  final权威性、缺final staging、未知字段、bool／float／越界值、外来nodeID及错误plan SHA；失败正文
  与私有异常不进入安全artifact。
- 7,919 planned node／3 report（23,757 hook调用）真实本机文件系统paired模拟运行5轮：关闭progress
  中位wall/CPU为0.000709/0.000709秒、0写；开启为0.008839/0.008817秒、最多6次实际原子写，单写
  p95最大0.000178秒。raw位于`logs/pr245-progress-benchmark-20261030-epoch4/benchmark.raw.json`，
  SHA-256 `e38a60580575d6e9a04dc6bcf08ebbbc47fae5d2faf5bcbc9b9dacbf4e170104`。这只证明本机等价报告流，
  不保证GitHub runner或完整CI时长。
- 未增加 workflow job、runner、worker、timeout 或依赖。

## 状态与剩余门

- 这是单次本机 profile，不保证 Linux CI 时长，不把旧 CANCELLED 或缺失 worker final 改写为通过。
- 最终完整 changed set 为15个文件；Router 选择 `full-delivery`／L4，组件为 research-web、
  unknown-boundary、documentation，保留 `unknown_impact_boundary` 与 Project Constraints／Research
  Web Checks 两个外部门。
- 本地 Project Constraints：PASS（15个文件，0 violations）；Router指定的精确L4 JavaScript四模块
  命令实际118 passed／0 failed／exit 0。完整raw为
  `logs/pr245-final-freeze-20261030-epoch7/router-l4-118.raw.log`（SHA-256
  `b33ff483defe790600c022e9504476ec7958189db8a6d3ea7badb802a410ca5c`），argv与exit原件SHA-256分别为
  `9aede590eeb05df8794bc175174ec9e264945beafeff11f1c94e7b72fbbbc69f`和
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`；命令前后15-source manifest
  均为`ac549ab47d440ed95dbb207a8edf0d3c781f5f18a882e41bbfce904d4e6da3b4`。epoch6误以Tabbit替换
  repository cross-platform所得116 passed raw保留为历史诊断，不再称完整L4合同。
  documentation governance：964 files／138 current／0 violations；Python生成索引已更新后 `--check`
  PASS；Ruff、Black、isort及`git diff --check` PASS。
- GitHub Project Constraints、Research Web Checks、Mac Bootstrap、Windows/Linux产品验收：`NOT_RUN`；
  由最终候选主任务按策略执行，不能由本机门或旧Mac b4证据替代。
- 未安装新依赖，未读取真实凭据，未运行真实模型、网络供应商、Office 或常驻更新。

## Architecture review

无新服务、API、存储、执行器或权限边；仅收窄现有 Catalog 静态依赖 metadata 扫描的内部实现。
