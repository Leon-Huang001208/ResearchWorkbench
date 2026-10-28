# 资产研究工作区

资产页现有图表与专题保持；下方提供研究摘要、可比对照、产业交叉三个可操作面板。
数据仅来自本人既有观察、不可变DataHub快照及显式选择的研究资料，不新增事实库、研究引擎或供应商。

## 操作

1. 当前证券观察就绪后，在工作区选择最多四个其他证券观察。主体与比较对象分别展示。
   选择具体报告记录，查看原值、报告期、单位、币种、口径、原件及manifest版本。
   不自动认定同行，不对不同期／单位／口径排名、换算或混算。
2. 选择已保存研究资料，或下载带当前真实原件引用的模板，编辑后使用“导入研究资料”。
   合法资料以标题、主体及实际文件保存日期显示；保存时间不表示发布日期。
3. 摘要标为分析观点／引用摘录。产业边标为“资料声明·待核验”，逐条查看原文和准确定位，
   不把来源声明当作已独立核验事实。
4. 明确截止日、问题与所需额外来源范围后，准备场景研究。比较对象、全部已选快照、资料文件
   及引用原件的同一版本一并冻结；仍需在问答明确发送。未勾选必要文件／网页范围时拒绝准备，
   不因选择文件而静默扩展会话权限。

## 严格资料格式

只接受版本 `asset-research-workspace/v1` 的JSON非执行数据，最多256KiB；未知字段和自报质量均拒绝。
顶层键为 `schema`、`subject`、`summaries`、`relations`。`subject` 为带交易所的证券身份。

- 摘要最多12条，每条 `id/title/text/evidence`，文字最多6000字符。
- 关系最多24条，每条 `id/from_identity/to_identity/relation/evidence`，至少一端必须是当前主体，
  不允许自环。证券使用交易所身份，行业使用显式分类命名空间；不会从名称猜身份。
- 每条引用最多4份，全文件最多64份。引用为 `source_session_id`、`reference={type,id}`、
  `sha256`、`locator`；type沿原档案协议 `dataset|file|source`，来源必须属于当前账号。
- `json-cell` 定位：`row` 为从0开始的原始JSON数组行、`field` 为准确字段、`quote` 为原值文本。
  非字符串原值采用 JSON 表达，数值不做格式化换算。
- `text` 定位：`start/end` 为UTF-8解码后从0开始的字符半开区间，`quote` 必须等于原文切片。
  不支持凭URL现场抓取、不隐式OCR或解读二进制文件；原件和定位不符即拒绝。

“下载研究资料模板”将本人现有金融快照的真实引用身份、哈希和字段定位填入；关系数组初始为空。
模板只有原件摘录，不自动形成研究观点或产业关系。可从输入区现有文件链产生同版本资料；
输出文件用 `.asset-research.json` 后缀可进入资料选择。选择之后仍逐项重验来源。

导入走窄入口 `POST /api/research/assets/research/import/{observation_id}`（multipart `file`），
要求来源观察会话已允许uploads，验证全部原件和定位后存于其原 `inputs/asset-research/`。
通用 `UPLOAD_EXTENSIONS` 不改变；JSON不获得可执行代码、任意文件路径或模型授权。

## 读取与冻结

`GET /assets/research/catalog?observation_id=...` 列出当前账号有界观察及明确资料文件候选。
`POST /assets/research/preview` 接受观察、比较观察列表及可选 `{source_session_id,file_id,sha256}`；
首次选择可省略hash，由服务器读回当前版本，后续冻结必须提交该实际hash。JSON正文不得自报
passed/incomplete/invalid。导入摘要始终未独立评估；引用当前canonical `outputs/research-report.json`
时，每个引用分别附上Host当前重验的source_quality、source_contract、source_task_id与
source_report_sha256。来源报告质量不转移给自由改写的摘要，多个来源不取最后一个或合并成摘要评级。

原件查看走 `/assets/research/evidence/{sid}?type=...&id=...&sha256=...`，只读本地已取得原件，
逐次鉴权和校验hash，不是URL代理；变化、撤权、缺失不替换为新版本。

原交接接口新增 `comparison_observation_ids`、`workspace_material`、显式 `source_scope`。
T1输入合同不变：material_ids列出选定dataset身份及 `file:<资料file_id>`。Host派生
subject/comparison/supporting_evidence角色；比较证券不能偷换为主体，资料文件不授予新来源。
原DataHub复制快照，其他已批准文本原件复制到目标 `inputs/page-evidence/`，保存完整祖先引用链。
读取、导出、再次交接和发送均回溯祖先；软删除保留核验，永久清理由原retention fence阻断。

## 验证边界

真实临时Host／Store／文件／快照和Chrome验证导入、保存后再次选择、摘要、比较、产业边、
准备研究及原基金交接。截图页面明确标记“隔离验收样本”，其中关系与数据是合成测试材料。
桌面键盘与窄视口已验；实体手机键盘、真实模型／供应商、生产常驻部署与跨平台保持NOT_RUN。
这不是对原站私有知识库或专有数值模型的复刻认证。


观察身份沿现有唯一别名解析器解析，合法六位证券别名仍可使用；不同主体和歧义代码拒绝。
同一观察或已选择比较观察的区块／数据集版本变化会立即清除旧预览并重新读取，保留问题、
截止日、比较选择与已勾选来源范围。迟到响应不能覆盖新版本；账户或主体变化不复用旧证据。

## 2026-10-28：T3组合包集成边界

资产既有workspace_material/bundle仍走原reader并锁对象；独立组合包可明确选择本人会话资料。已登记来源选择路径才派发新reader，旧asset bundle不按扩展名豁免。九包预览后仍走原handoff、Send和档案显式关联，不自动更新thesis/quality，制品保存不代替报告质量。
