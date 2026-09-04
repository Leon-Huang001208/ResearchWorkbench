(function () {
  'use strict';
  const app = window.AlphaPrototype;
  let activePage = null;
  function parseHash() {
    const raw = location.hash.replace(/^#/, '') || '/market-home';
    const [pathname, search=''] = raw.split('?');
    const query = Object.fromEntries(new URLSearchParams(search));
    let pattern = pathname;
    let params = {};
    if (/^\/assets\/[^/]+$/.test(pathname)) { pattern='/assets/:assetId'; params.assetId=decodeURIComponent(pathname.split('/')[2]); }
    if (!app.pages.has(pattern)) pattern='/market-home';
    return { pathname: pattern === '/market-home' && !app.pages.has(pathname) ? '/market-home' : pathname, pattern, query, params };
  }
  function renderRoute() {
    const parsed=parseHash(); const page=app.pages.get(parsed.pattern); const root=document.querySelector('#page-root');
    if (!page || !root) return;
    try {
      if (activePage) activePage.unmount();
      app.state={...app.state,route:parsed.pathname,routePattern:parsed.pattern,query:parsed.query,params:parsed.params,activeAssetId:parsed.params.assetId || app.state.activeAssetId,activePackKey:parsed.query.pack || app.state.activePackKey};
      document.title=`${page.title} · Research Workbench`;
      root.innerHTML=`<section class="page-frame" data-page-route="${parsed.pattern}">${page.render(app.state)}</section>`;
      activePage=page; page.mount(root,app.state); window.AlphaShell?.sync(app.state); window.AlphaJourneys?.render();
      window.scrollTo({top:0,left:0,behavior:'auto'}); root.focus({preventScroll:true});
    } catch (error) {
      console.error('[AlphaPrototype] route render failed', error);
      root.innerHTML='<section class="page-frame"><div class="state-banner danger"><div><strong>页面渲染失败</strong><span>错误已记录，请切换页面后重试。</span></div></div></section>';
    }
  }
  app.router={
    start(){ window.addEventListener('hashchange',renderRoute); renderRoute(); },
    navigate(route){ location.hash=route.startsWith('/') ? route : `/${route}`; if (location.hash === `#${route}`) renderRoute(); },
    refresh:renderRoute,
  };
})();
