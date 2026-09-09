(function () {
  'use strict';
  const app=window.AlphaPrototype;
  const products=[
    ['/market-home','市场','⌂','market'],['/themes','主题','◇','theme'],['/assets/AU-DEMO','资产','▤','asset'],
    ['/fingpt','FinGPT','✦','fin'],['/claw','Claw','♜','claw'],['/watchlists','自选','☆','watch'],
    ['/research-library','研究库','▣','library'],['/capabilities','能力','⚙','core'],
  ];
  const moduleItems={
    market:[['市场总览','/market-home'],['重要事件','/market-home?focus=events'],['历史快照','/market-home?date=2026-08-31']],
    theme:[['主题目录','/themes'],['黄金','/themes?pack=gold'],['航天航空','/themes?pack=aerospace'],['光伏','/themes?pack=solar'],['AI 基础设施','/themes?pack=ai-infra']],
    asset:[['资产详情','/assets/AU-DEMO'],['同类比较','/assets/AU-DEMO?tab=peers'],['资产事件','/assets/AU-DEMO?tab=events']],
    fin:[['新研究','/fingpt'],['运行中','/fingpt?view=running'],['历史会话','/fingpt?view=history']],
    claw:[['新任务','/claw?action=new'],['运行中','/claw?view=run'],['Agent Teams','/capabilities?tab=teams'],['日程','/capabilities?tab=schedules'],['Skills','/capabilities?tab=skills']],
    watch:[['核心自选','/watchlists'],['提醒规则','/watchlists?tab=rules'],['通知收件箱','/watchlists?tab=inbox']],
    library:[['研究项目','/research-library'],['证据','/research-library?tab=evidence'],['Claims','/research-library?tab=claims'],['Artifacts','/research-library?tab=artifacts'],['研究笔记','/research-library?tab=notes']],
    core:[['Runtime','/capabilities?tab=runtimes'],['Skills','/capabilities?tab=skills'],['Agent Teams','/capabilities?tab=teams'],['MCP 授权','/capabilities?tab=mcp'],['日程','/capabilities?tab=schedules']],
  };
  function activeModule(state){ const page=app.pages.get(state.routePattern); return page?.module || 'market'; }
  function topbar(){ return `<div class="brand"><img src="assets/research-workbench-logo.png" alt=""><span>Research Workbench</span></div><label class="global-search"><span class="sr-only">全局搜索</span><input placeholder="搜索市场、资产、主题或研究…"></label><div class="top-actions"><button class="top-action" data-action="research"><span>研究空间</span> ▥</button><a class="top-action" href="../merged-platform-blueprint/index.html"><span>架构蓝图</span> ↗</a><button class="top-action mobile-keep" data-action="tweaks" aria-label="原型设置">⌘</button><span class="profile-dot">L</span></div>`; }
  function productNav(state){ return products.map(([route,label,icon,module])=>`<a class="product-link ${activeModule(state)===module?'active':''} ${module}" href="#${route}" data-product="${module}"><span class="nav-icon">${icon}</span><span>${label}</span></a>`).join('')+'<span class="product-spacer"></span>'; }
  function sidebar(state){ const module=activeModule(state); const title=products.find((item)=>item[3]===module)?.[1] || '工作台'; return `<div class="module-heading"><strong>${title}</strong><button class="icon-button" data-action="close-module" aria-label="关闭模块导航">×</button></div><span class="module-label">工作区</span><div class="module-group">${(moduleItems[module]||[]).map(([label,route],index)=>`<a class="module-item ${index===0?'active':''}" href="#${route}"><span>${label}</span>${index===1?'<span class="count">3</span>':''}</a>`).join('')}</div><div class="module-group"><span class="module-label">最近</span><button class="module-item"><span>黄金产业链供需</span><span class="count">今天</span></button><button class="module-item"><span>AI 收入质量验证</span><span class="count">周一</span></button></div>`; }
  function research(state){ const tab=state.researchTab; const content={sources:['世界黄金协会 · 供需季度报告','国家统计局 · 工业数据','交易所公告 · 已验证'],evidence:['E-041 · 供给增速连续回落','E-038 · 央行购金保持高位','E-025 · 实际利率边际下降'],claims:['C-012 · 上游供给弹性仍低','C-009 · 资金与实物需求共振'],notes:['黄金主线跟踪 · v4','宏观风险清单 · v2'],artifacts:['黄金研究备忘录.pdf','事件影响矩阵.xlsx']}[tab]||[]; return `<div class="research-head"><div><strong>研究空间</strong><div class="card-subtitle">Workspace · 宏观与贵金属</div></div><button class="icon-button" data-action="research" aria-label="关闭研究空间">×</button></div><div class="research-tabs">${['sources','evidence','claims','notes','artifacts'].map((id)=>`<button class="research-tab ${tab===id?'active':''}" data-research-tab="${id}">${({sources:'来源',evidence:'证据',claims:'Claims',notes:'笔记',artifacts:'产物'})[id]}</button>`).join('')}</div><div class="research-body">${content.map((item,index)=>`<article class="research-item"><span class="eyebrow">${tab.slice(0,-1) || tab} ${String(index+1).padStart(2,'0')}</span><p>${item}</p></article>`).join('')}</div><div class="research-footer">研究内容与事实区隔离 · 所有条目可追溯 Run 和来源</div>`; }
  function attach(){ document.body.addEventListener('click',(event)=>{ const action=event.target.closest('[data-action]')?.dataset.action; if(action==='research') app.setState({researchSpaceOpen:!app.state.researchSpaceOpen}); if(action==='close-module') app.setState({moduleDrawerOpen:false}); if(action==='tweaks') app.setState({tweaksOpen:!app.state.tweaksOpen}); const tab=event.target.closest('[data-research-tab]')?.dataset.researchTab; if(tab) app.setState({researchTab:tab}); }); }
  window.AlphaShell={
    init(){ document.querySelector('[data-shell="topbar"]').innerHTML=topbar(); attach(); this.sync(app.state); },
    sync(state){ document.querySelector('[data-shell="product-nav"]').innerHTML=productNav(state); document.querySelector('[data-shell="module-sidebar"]').innerHTML=sidebar(state); document.querySelector('[data-shell="research-space"]').innerHTML=research(state); document.body.classList.toggle('research-open',state.researchSpaceOpen); document.body.classList.toggle('module-open',state.moduleDrawerOpen); const toast=document.querySelector('#toast-region'); toast.innerHTML=state.toast?`<div class="toast">${app.escape(state.toast)}</div>`:''; },
  };
  app.subscribe((state)=>window.AlphaShell.sync(state));
})();
