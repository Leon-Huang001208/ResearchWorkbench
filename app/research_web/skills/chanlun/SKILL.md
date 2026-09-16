---
name: chanlun
description: 对单一标的日线执行确定性的严格分型与非递归笔结构研究。
---
# 缠论确定性结构研究

运行 `scripts/calculate.py <relative-input.json>`。每次只接受一个标的、最多 5,000 根日线。本版本只实现公开透明的“严格局部分型 → 交替确认笔”子集：中心高点/低点必须严格超过指定跨度两侧；同型候选仅保留唯一更极端者；异型候选必须满足最小间隔。相等极值平台、同一中心同时为顶底或过近反向分型均返回 `ambiguous_structure`，不得主观消歧。

算法单次顺序扫描，不递归、不枚举组合，也不声称覆盖中枢、背驰等完整缠论体系。历史少于确认跨度返回 `insufficient_history`；日期、证券身份、OHLC、provider、单位和前复权必须等价。所有记录必须属于同一非空 `asset_id`，结果顶层必填并原样回传该唯一身份；任一记录身份不同均返回 `data_not_equivalent`。输出还包含样本、条件、歧义反例、失效条件与截止日，是研究结构信号，不是交易或下单指令。

原候选 Skill/template 在指定来源树中不可用，provenance 明确 `source unavailable`，未猜测完整 SHA-256；当前 DataHub 映射 `callable=false`、catalog 初始 disabled。只有真实 macOS Wind/Excel 外部宿主登记器签发并绑定当前不可变版本的 v2 HMAC comparison receipt 才能启用。
