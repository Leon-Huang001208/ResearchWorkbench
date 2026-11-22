# C0：未知来源角色的最小版本合同

任务 `seek-packs-20261027-7bda5752`；基线 `6334130e38313824d576cc51a1cf3a60a4622dd8`。
macOS Mac mini Web开发，独立worktree；仅本地实现/提交，交root独立SPEC→QUALITY。
本切片是C2真实source投影的必要前置，不代表C1/C2完成，更不是T3或全部62/78完成。

## 事实与结果

原Dossier source只可信地保存URL/title/fetched_at/hash及最多自然日发表证据，没有语言、地域、
原创/转载/翻译角色。不得把“捕获到原件”映射为原创。经root明确批准：source-version角色
增加unknown；去重发现unknown明确列source_role_unknown缺口，每版本输出保留真实角色，
不推断转载关系或滞后。原original/reprint/translation算法保持。

仅deduplicate_source_versions及research-prep/global-opinion方法升1.1.0；其余七包仍1.0.0。
新manifest v2明确引用record contract版本2和output contract v2的路径/hash。旧v1输出/记录
合同以633原canonical bytes留在包内，SHA分别为
`de146921f14565d590c988ab4711528759b2f7ad45c141487106d1fb470790fd` /
`04f0970ff6aa798c28f5b65906f5eb5a94533882b595299f7b3f8116c804be53`。

Host读回按私有execution绑定及冻结resource manifest解析唯一固定v1/v2合同；校验manifest
hash、closure、全部resource声明hash和合同实际bytes，再以原记录schema检查封印输入。
缺失capability/file_bindings、未知合同版本、篡改及用v2替换v1均拒绝；结果不能自选schema。
没有修改Native输出文件协议、旧报告门、旧18gates、Catalog迁移或只读等价政策。
旧未发布pack跨语义代码不能执行或获得伪equivalence；既有生产非pack档案与prefix-relocation
回归沿原门。没有增加通用历史脚本迁移器。

## 旧样本来源与可移植性

`tests/research_web/fixtures/pack-633-v1/`保存改动前捕获的633完整冻结package、合成输入、
实际旧冻结writer/calculator执行所得receipt/full-result/manifest、execution与provenance。
11个冻结脚本/向量已与git633源码逐字核对，逐项SHA在provenance。生成epoch为本轮C0 RED
之后、resource变更之前的旧package捕获，实际生成在本机受控临时目录，不是线上档案。
未用新产物删字段制造历史输出，也未事后改旧runtime原字节。
测试只重建相对文件、按原封印合同只读核验，不执行旧脚本、不要求旧绝对路径或interpreter
存在。新v2执行另用当前package。Fixture不授予任何真实源权限。

## 实际验证

- RED：unknown source_role被旧schema拒绝、两个包仍1.0.0，2 failed；`c0-red.log`。
- 第一目标GREEN：新unknown原子/新v2与旧v1产物读回、输出审计、九包资源版本，57 passed，
  26.89s；`c0-version-green.log`。随后去除低层fixture专用fallback，改低层writer/audit测试
  为真实冻结package file_bindings；其最终回归另列下方。
- 使用现有hatchling缓存实际构建wheel，2份旧v1JSON入包且与源码bytes相同；C1临时文件
  不在wheel，`wheel-resources.json`。这是格式整理前打包证据，最终candidate由root重建。
- 本轮未安装依赖；pytest借用已登记uv缓存PYTHONPATH，不把最早环境缺pytest当RED。

所有日志/argv/受控环境/PID/UID/临时根与SHA在`logs/research-packs-c-20261027/`。
C1三个未提交文件暂停移入`/tmp/parity-c1-pending-7bda5752`，不会进入C0提交或wheel。
真实模型、供应商、source live、部署、服务、CI、跨平台原生仍NOT_RUN；C2真实来源mapper及
完整Host→DSH→sandbox链尚待本必要版本子任务独立审查后继续。

## 本地最终回执

邻近单轮 **138 passed, 1 warning，376.42s**，runner PID77796/UID501；包含历史Dossier、
prefix-relocation/多hop拒绝、非pack保全、纯核与新合同/256行完整writer/审计。
日志SHA256 `64ad35ffcc646a903f3f5e9cdf7a72084a5db148a233d84e482cbad7324a4ebb`。
格式后版本/冻结合同/审计/完整writer短验 **48 passed，8.84s**，runner PID88965/UID501；
日志SHA256 `ffaae397f5eedf0b4c35211688ddd7ef46e071afb5bc2b8f4af0b510acb264dc`。
Ruff、Black十文件、isort、pyindex生成并check、git diff --check实际通过。
首次格式工具环境缺mypy_extensions的预检保留preflight-static日志；补现有缓存路径后通过，
无安装。最初pytest环境缺失、临时生成路径/var符号链接被旧writer拒绝的探索失败未作PASS；
最终旧fixture生成与633逐字校验、真实v1/v2产物读回已按上述测试另证。

4个本轮确切临时根在UID/归属/无open复查、515文件归档及hash读回后回收；回收字节至少
1,532,235,047。首次删除遇只读版本目录失败，保留已验证归档，并仅对owner本人本轮目录
恢复写权限后完成；首根回收字节因此是剩余量下界，没有编造原总量。
`c0-owned-closeout.json`记录原路径/身份、归档SHA、读回文件哈希、目录写权限恢复与结果。
旧50探索根、其它任务资源、Docker、源worktree均未清理；全任务project closeout仍由root
独立判定，不把本C0临时资源完成称为全项目cleaned。C0仅候选，SPEC/QUALITY仍待root。
