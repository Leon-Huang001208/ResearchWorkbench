(function(){
  'use strict'; const app=window.AlphaPrototype;
  function attachResponsiveShell(){
    const wideViewport=window.matchMedia('(min-width: 1440px)');
    const syncResearchSpace=(event)=>app.setState({researchSpaceOpen:event.matches});
    if(typeof wideViewport.addEventListener==='function')wideViewport.addEventListener('change',syncResearchSpace);
    else wideViewport.addListener(syncResearchSpace);
  }
  function init(){
    try {
      document.documentElement.dataset.theme=app.state.theme; document.documentElement.dataset.density=app.state.density;
      window.AlphaShell.init(); attachResponsiveShell(); window.AlphaTweaks.init(); window.AlphaJourneys.render(); app.router.start();
      window.addEventListener('error',(event)=>console.error('[AlphaPrototype] uncaught error',event.error||event.message));
      window.addEventListener('unhandledrejection',(event)=>console.error('[AlphaPrototype] unhandled rejection',event.reason));
      console.info('[AlphaPrototype] ready',{pages:app.pages.size,mode:app.state.dataMode});
    } catch(error) {
      console.error('[AlphaPrototype] bootstrap failed',error);
      const root=document.querySelector('#page-root'); if(root)root.innerHTML='<section class="page-frame"><div class="state-banner danger"><strong>原型启动失败</strong></div></section>';
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
