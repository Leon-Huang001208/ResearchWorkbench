# B1 Python HIGH修波：实际导入闭包与必需日期校验

base `f0852e1bce71b30cf49a5d72523eb37fac7ade2a`，任务 `seek-packs-20261027-7bda5752`。
macOS Mac mini Web功能开发；仅scope commit回root独立复SPEC／Python，JS blob与f085相同可复用其TS proof。
不改UI／140映射、原18 gate、旧8 scenario、SourceAuthority／供应商／账户／服务／部署／CI／push；无新依赖或网络/LLM调用。

## 真实缺陷、RED与范围决策

原runtime v2只绑定六个分发，遗漏jsonschema._format实际执行的idna等optional imports。
独立审查的protectedroot `/private/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-b1-pythonreview-idna-mofkdn6r/`
只读核验，未修改或清理。自有真实fresh subprocess复制idna并加marker，分别覆盖sys.path优先、
移除路径后的preloaded root、相对子模块shadow及另一optional fqdn：marker确实写入，旧runtime仍接受，
**4 failed in0.63s**。`/tmp/rwb-b1-importfix-91c7d4-red.log`保留原始失败，不用假stdout或mock准入passed。

进一步发现原受管jsonschema没有date-time checker（只有date/email等九个），不是本波删除了它。
真实原checker接受坏日期 `2026-02-30T12:00:00Z`，新profile拒绝；证据
`logs/research-packs-b1-importfix-20261027-91c7d4/format-correction-proof.json`，SHA256
`729f3c68cd1629fde59a2a0979787b32a739b7d43163d3aee3a0e3aa45c2bbab`。

Root明确批准本波最小A6验证层delta：新增冻结stdlib date/date-time profile，`contracts.py`只替换
实例checker并检查固定schema；不能继续声称所有A6字节未改。数学算法atoms/bundles/limited、
record schema、原baseline.json/contracts.json以及纯核公开方法/限额不变，实际git diff已核对。
固定schema不含$ref，远程resolver不属于实际验证功能；全函数AST会走requests动态导入，不能猜安全。
Root批准用Native严格运行时门禁止该未支持lazy/dynamic路径；不是声称任意未来函数体都闭合或可执行。

## 最小修复与权限

- runtime schema v3，lock projection v2：whole web.lock原字节/SHA不改，增加锁内现有idna3.19精确版本；
  当前受管集合七分发，但集合不是安全推断。各分发实际package/data/native/metadata/pyc独立枚举、hash、
  origin和原安装账簿排除规则保持；新代码不因RECORD漏列而漏hash。原六包反例保留，新增真实idna复制
  的source/新增transitive文件/pyc/METADATA/symlink正反例。没有安装或手写替代第三方实现。
- 冻结stdlib-only `pack_import_policy.py`：递归实际module-time optional/相对/transitive导入图，检查
  当前sys.path搜索origin及全部preloaded依赖子模块的file/spec/cache/path；标准库同名影子也拒绝。
  可见但未绑定的module-time optional不能靠checker名字相同认证；未知module-time动态import failclosed。
  未绑定lazy/dynamic imports在Native实际触发稳定拒绝；不把AST中存在解释为安全或支持。
- 固定Host launcher在calculate/jsonschema前安装精确MetaPath白名单与origin验证，缓存污染先拒绝；
  未绑定requests（包括importlib动态导入）不能执行，原本不存在optional仍不存在。仅允许已hash的精确
  本地模块、绑定分发、真实stdlib origin；不开放任意core/app或外部模块。Host不改全局sys.path/modules/hooks。
  仅scenario literal分支省去普通report SDK预载；旧普通/weekly仍原bootstrap，输入/输出/Seatbelt/bridge权不扩大。
- 冻结 `format_profile.py` 和实例checker在Host输出审核与Native核心共享，hash连同importguard进入资源
  与runtime.identity。每处声明format确实检查；拒外部/dynamic schema和未知format。严格日期calendar、
  四位年、T/Z或合法offset、秒/至多6位小数；拒naive/date-only/basic-date/空格/坏日期/坏offset/闰秒与
  UTC转换越界。明确RFC3339严格子集，非完整闰秒实现。没有修改全局FormatChecker registry。
- 资源完整manifest包括新profile/guard，仍128files/320literal/64KiB/16MiB/50k等原限额；旧runtime v2或
  profile/guard/依赖变化不会静默迁移，历史证书仍重新比当前真实identity，旧执行仍version-conflict。

## 探索结果与最终闭包

近定点profile/import/current identity **41 passed,1wheel skipped in3.35s**。探索近闭包初次
**144 passed,2 failed in138.60s**：pack sandbox原预载research_report被新门正确拒绝；另一次探索期间
编辑guard导致同轮资源字节不同，旧证前置预期变为content_changed。未改断言抢绿；限定pack bootstrap
省去SDK预载，停止source变动后两项原测试 **2 passed in9.17s**。所有失败日志保留。

最终以新wheel+固定source运行原369范围及新import/format/weekly admission；精确argv/env、PID/UID、
duration、日志SHA及own opaque basetemp在
`logs/research-packs-b1-importfix-20261027-91c7d4/final-python-receipt.json`；完成后再追加计数。
真实Host/NativeRunner/Seatbelt无LLM整链保留；TestClient桥仅transport，不把fixture来源声明成真实厂商质量。
当前只有BaoStock价格子集，其他九包来源gaps/partial/NOT_RUN不升级。完整数据与质量独立，保存文件不是研究通过。

实际本地wheel构建使用现有hatchling缓存；wheel内包含lock投影、新profile/guard，并用无checkout的installed-like
路径加载测试，不安装新包。安装器/requirements/锁/CI无需变更；干净macOS安装、Doctor、健康/常驻服务、
Windows/Linux、UI/140、真实模型/供应商/MCP账户仍NOT_RUN。Mypy仍因既有librt缺失未运行，未安装。

本波只显式 `rwb-b1-importfix-91c7d4-*` basetemp及final runner所登记新opaque根；旧50/root的其他评审目录
不扫描/不删除。必要logs/marker/hash归档读回后只回收自己已核UID/dev/inode/无openfiles的测试根；
final runner自有根按实际receipt归档结果/Native证据后清理，实际清理事实追加于下文。

补充探索流水（不是最终绿色）：firstgreen 1FAIL/5PASS/1SKIP，根因全函数扫描见未支持requests，
已按root明确批准的固定schema+Native runtime deny设计收敛；native初次8FAIL/14PASS/1SKIP，
其中7项是资源拼接时encode_file参数错误，1项为Native bootstrap真stdlib sitecustomize被误拒；
修正参数并仅允许真实stdlib origin后native2 1FAIL/19PASS（原不存在optional也被ValueError，
此项改为仅明确absent且无spec的ModuleNotFoundError，不允许实际外部模块），native3 10PASS。
所有具体原日志归档，未降低必需format/checker/权限来换绿。另补真实 retained shadow：_format
保留外部idna对象后，恢复sys.modules/移走sys.path仍可漏过，仅module表不足；自有marker负例
RED1FAIL/12deselected/0.40s，随后必须核实际被引用模块对象的origin，不能把表重置视为安全。

广泛闭包第一轮实际 **460 passed,16subtests passed,1旧warning in1036.18s**；runner62886／
pytest62888／UID501，48产物归档并hash读回后自身opaque temp清理true。日志SHA256
`21547e4be77eba6bfb0d31a66188c3343202a8d9c9ee5fea8b083ad5ba8fa0f8`；回执SHA256
`bb01de45975ca75b9017a68741ddf730971f657e8347aa93930b865d1f23ab3e`。
该轮明确早于retained-object引用核验及as_of额外合法offset验证，不拿该结果冒充最终源。
之前实际wheel已另存 `wheel-before-retained/`，hash与边界记录于wave-boundary.json，未覆盖原产物证据。

补充修正没有改Host全局：重验实际保留的module对象及function/class代码origin，恢复module表也不能
掩盖外部对象；绑定库本身生成的attrs/typing函数仍属于受管generator信任边界，不声称能对任意
被攻陷Host中的Python对象做不可伪造远程证明。profile补齐每处schema format，也以同一valid_instant
检查参数instant的合法offset；数学计算不改。真实retained-object RED→GREEN后import/profile/真实Native
合法与坏日期控制 **46 passed in12.14s**。

最终源新wheel与受影响闭包另记 `candidate-python.log` / `candidate-python-receipt.json`：
全部pack闭包、actual Host/DSH/Seatbelt、input/output、historycert、迁移、wheel和纯核相近用例。
未再次重跑第一轮已过且此后未改的旧Dossier／weekly／通用门；JS blob仍与f085相同。

本波11个explicit探索根已按实际创建tool call（原session JSONL行／call_id／逐行SHA）逐根
匹配；每根核UID/dev/inode、`/usr/sbin/lsof -nP +D`真实return1且stdout/stderr均空、无非空锁。
日志copy+SHA读回与实际marker内容/hash归档后，仅调自身owner目录权限并清理11/11。
`exploration-resource-receipt.json` SHA256
`e708169a4685ac8bdb75ae991de3c848b0998692e95fb1dd21c18d495c57b273`；未知/旧50/独立review protectedroot未碰。

## 最终候选与静态证据

最终源受影响闭包 **269 passed,1旧warning in611.23s**，exit0，runner计时611.486s。
原16subtests属于之前广泛460轮，不混称本次269的子用例。最终日志SHA256
`dcc05e73c9a3eca726d253407dbc928ac9a1b3785e9e83e82f3151d422635b02`；receipt SHA256
`fe56140027cf6ff82e2adebb240eeea98442195ea7b60715476de24b3c12a710`。
精确argv/env/PID/UID见candidate receipt；48份最终Native／full-result证据独立前缀归档，逐hash
读回后final candidate自有opaque根清理true，原广泛轮证据未覆盖。

Ruff、Black14files、isort、pyindex、diff检查和数学/record schema/baseline/contracts字节保全、
相对f085的JS字节等价共7项实际命令全部exit0，static log SHA256
`6fe9aa8b69ac27eca5c99207f3b8ea00d26d4c76f512df84d8da7d1a8fea27bc`；receipt SHA256
`b99c03f0f083d7f82fab6efc37f55b1405db6981c50c604882b763a76e789424`。
新wheel SHA256 `2f329a62fc663a5b0159d4e5a3c0d8f05b173c60755da29c8116c02fc9822f7b`，
9个关键实际wheel文件与当前源逐字节一致，proof SHA256
`d0bb4f71391beb75bc26104cd7cbc15ae810824b82d6abc7db880a8ab0012f1a`；无checkout installed-like
实际执行包含在269闭包，未跳过。远端CI/clean setup/Doctor仍NOT_RUN，不能由wheel静态证明代替。

这是本地安全修复候选，仍交root独立复PythonQUALITY及受影响SPEC；不自行标B1整体Approved或计划完成。

最终candidate runner PID86859／pytest PID86904／UID501；自有根为`/private/var/folders/rz/f7lsl4nn2bl0lpsfqyylp1jh0000gn/T/rwb-b1-importfix-91c7d4-candidate-s68f1q9b`，已清理。另11份原/tmp日志及4个本任务操作脚本在copy/hash读回、UID/dev/inode/regular/nlink1和exact-file lsof无open复查后回收15/15；脚本副本仅以.txt留在证据目录。temporary-file receipt SHA256 `18d31cce7adc9c24c023c0d93b24de0a696bb5c0c89f3e4b437e31e09035481d`。仅necessary logs/wheel/receipts留在本WT等root复评归档。
