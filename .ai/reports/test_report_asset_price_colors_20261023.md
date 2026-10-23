# 资产价格红绿显示

任务asset-price-colors-20261023；macOS Mac mini，Web功能开发。用户追加要求开高低收、涨跌幅参考Wind。

沿用已批准精炼布局、万亿格式、图表生命周期及数据。开高低收相对前收分别着色，不按整根蜡烛方向套色；当前价使用同快照前收/来源涨跌，涨跌额和幅各自按正负。采用现有主题danger/green变量以保持明暗对比，只作用于资产数值，不改变风险/成功状态语义。价格无效/非正、涨跌零/缺失保持中性。历史选择与局部更新重用纯分类器，updateAssetSummary同步class。

本地资产JS184PASS，约1.79秒。独立评审指出无前收且零价会借来源跌幅着绿，已加有效正价格guard和回归。最终Router、独评绑定、宽窄明暗、同候选三CI/macOS干净安装、固定新profile及常驻验收另行记录；不预先标为已部署。此前精炼布局v6已部署0e0022ac，保全true，本颜色补丁尚未部署。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅既有资产组件数值class与主题变量，原DOM层次、搜索、页签与图表实例不变，无新页面/服务；现有UI图仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"仅前端投影暴露同快照前收并格式化数值，不改HTTP/冻结/Provider或研究引擎；原观察和数据流图仍准确。","diagrams":[]} -->
