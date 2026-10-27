# 再生字节码编码兼容修复

- 宿主：macOS；任务类型：既有资源收尾功能缺陷修复。验收范围为本机 Python3.9/3.12及用户单独授权的隔离3.14离线合同；Ubuntu 系统 Python 的最终 CI 由主控制任务重新绑定。不改系统Python/PATH/服务，不安装其他包，不push/部署或操作其他平台产品。
- 起点：PR243 集成候选 `8f5288ca76e12f5db0056320ef2608c10c2bca9d`。Project Constraints run `40384650499` 的资源模块15项通过，再生模块4项出现1 ERROR/1 FAIL，均先遭 `closeout_regenerated_bytecode_unknown`。全日志只确认 ubuntu-26.04、使用系统 `python3`；没有 Python 版本输出，不能认证实际为3.14。
- 首轮仅更换标准编码器的提交3e6500e1在本机3.12通过，但后续CI `40440907851` 仍出现同两例失败，明确该首轮修复不足。经用户明确授权，在任务内用 uv0.11.32 `--no-config --cache-dir TASK/cache python install 3.14 --install-dir TASK/install --no-bin --no-registry` 安装CPython3.14.6；不增加仓库依赖或修改workflow。
- 真实3.14.6复现原6项的1 ERROR/1 FAIL。可信临时文件诊断的24组合（简单/嵌套×timestamp/hash×opt0/1/2×cold/warm）均为actual首字节e3、expected63及引用表索引差，递归全部co字段相等；在函数域保持额外tuple引用后24组payload全部逐字节相等。模块顶层域没有同样失败，因此仅顶层实验会掩盖3.14函数局部借用引用差异。
- 修复：仅在可信重编译 code 编码期间显式以tuple保持额外引用，再走py_compile同路标准编码器，仍与原缓存逐字节比较；编码器不可用时日志记录并拒绝。不加载不可信 marshal、不执行缓存、不改变源文件/头部/大小/路径/清单与未知文件拒绝门。诊断脚本的loads仅处理其当次私有TemporaryDirectory内真实py_compile与可信compile字节，不接收外部缓存参数。
- 测试保留真实 py_compile 正例、伪造字节负例、未知文件竞态；新增编码器不可用拒绝，以及真实 py_compile 的另一源码 payload（相同 dfile）与尾随业务数据保留。未使用自造 canonical pyc 代替真实正例。

## 实际验证及证据

解释器：系统3.9.6、既有3.12.13/3.12.14与用户授权隔离3.14.6；只安装该临时runtime，没有安装其他依赖。

- `python -m unittest discover -s tests/research_web -p 'test_iteration_regeneration.py' -v`：RED 为新增编码器缺失负例未抛 ResourceError（5项中1 FAIL）；修改后6项全部通过。
- `python -m unittest discover -s tests/research_web -p 'test_iteration_resources.py' -v`：15项通过。
- 原始日志：`logs/seek-parity-ci-40384650499-full.log`、`logs/seek-parity-ci-40384650499-regeneration-failed.log`。
- 本机日志：`logs/seek-parity-regeneration-baseline-312.log`、`logs/seek-parity-regeneration-red.log`、`logs/seek-parity-regeneration-green.log`、`logs/seek-parity-regeneration-adjacent.log`、`logs/seek-parity-marshal-reference-variants.log`。
- 初次使用上述 venv 运行 black/isort/ruff 时模块缺失，未安装；随后使用既有 uv 缓存中的 black/isort 及 ruff binary，两个改动 Python 文件的 black/isort/ruff 检查全部通过，black未改字节。
- `node --test tests/javascript/iteration_closeout.test.mjs`：3项通过（`logs/seek-parity-regeneration-closeout-node.log`）。`node scripts/check_documentation_governance.mjs --project .`：零违规（`logs/seek-parity-regeneration-doc-governance.log`）。
- 另尝试 `python -m pytest` 时该 venv 缺 pytest，未安装；因此 pytest 未执行，不能宣称通过。原 CI 使用的 unittest 两模块已实际通过21项。

## 未完成项与风险

3.14.6真实RED/GREEN：原6项1 ERROR/1 FAIL；新增函数域timestamp/hash及三optimization真实py_compile回归后7项中1 FAIL/7 ERROR；显式引用修复后7项（含6矩阵subtests）全部通过。日志为`logs/bytecode-diagnostic-isolated-3146-{unittest-red,matrix-red,green}.log`。24组合及函数/模块域对照为`logs/bytecode-diagnostic-isolated-3146-reference-matrix.jsonl`和`logs/bytecode-diagnostic-3146-explicit-reference{,-function}.jsonl`；最小可执行诊断脚本为`logs/diagnose-iteration-bytecode.py`。

完整模块复验：Python3.12.13、3.12.14、3.14.6各自的再生7项（含6矩阵subtests）与资源15项均通过；Nodecloseout3项通过。日志为`logs/bytecode-repair2-{homebrew31213,bundled31214,isolated3146}-{regeneration,resources}.log`和`logs/bytecode-repair2-closeout-node.log`。定点black/isort/ruff及文档治理复核日志为`logs/bytecode-repair2-format-final.log`与`logs/bytecode-repair2-doc-governance.log`。

按要求也尝试系统3.9.6完整模块：再生7项报12 errors、资源15项报2 errors，分别为系统py_compile产生的缓存路径遭原alias/outside-task门拒绝，以及缺少`hashlib.file_digest`。项目`pyproject.toml`明确requires-python>=3.11，不扩围适配3.9或放宽路径门，不能宣称3.9项目回归通过。3.9仅独立可信字节诊断24组合相等；完整失败日志保留在`logs/bytecode-repair2-system396-{regeneration,resources}.log`。

runtime来源为Astral官方python-build-standalone 20260718 macOS arm64 CPython3.14.6；根目录`.superpowers/diagnostic-runtimes/diag-mvq3p7qh-blut3l55/`，诊断时69,450,108 bytes/1813文件。来源URL、目录dev/inode/uid、tree与python SHA256保存在`logs/bytecode-diagnostic-runtime-manifest.json`；安装日志`logs/uv-python314-diagnostic-install.log`。按授权先保留供独评复验，最终归档必要日志/来源/hash后仅回收该runtime及其任务内缓存，不复制binary。

上述证明本机CPython3.14.6同症状及修复；原CI实际补丁版本与payload没有输出，不冒充已取得原runner原件。最终 Router、独立 SPEC/QUALITY 评审、原三CI及同候选Mac安装由主控制任务继续执行；此报告不把本机通过改写为 Ubuntu、跨平台或常驻验证。使用 CPython 私有标准库编码器是有界兼容依赖，缺失时明确拒绝，不回退到弱校验；显式引用的兼容性只认证实测解释器。

官方机制参考：[CPython py_compile](https://github.com/python/cpython/blob/3.14/Lib/py_compile.py)、[标准编码器](https://github.com/python/cpython/blob/3.14/Lib/importlib/_bootstrap_external.py)、[marshal 引用标记](https://github.com/python/cpython/blob/3.14/Python/marshal.c)。
