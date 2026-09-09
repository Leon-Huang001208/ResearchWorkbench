(function () {
  'use strict';
  const demoStates = ['default','loading','empty','partial','stale','unavailable','quarantined','error','permission_denied','blocked_runtime'];
  window.AlphaPrototype = {
    pages: new Map(), listeners: new Set(), demoStates,
    state: {
      route:'/market-home', routePattern:'/market-home', params:{}, query:{}, theme:'light', density:'compact',
      researchSpaceOpen:innerWidth >= 1440, moduleDrawerOpen:false, demoState:'default', dataMode:'live-first',
      activeWorkspaceId:'workspace-demo', activeAssetId:null, activePackKey:null, activeJourneyId:null,
      journeyStep:0, researchTab:'sources', tweaksOpen:false, runState:'idle', researchQuestion:null, toast:null,
    },
    setState(patch) {
      this.state = { ...this.state, ...patch };
      for (const listener of this.listeners) {
        try { listener(this.state); } catch (error) { console.error('[AlphaPrototype] state listener failed', error); }
      }
    },
    subscribe(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener); },
    registerPage(route, page) {
      if (this.pages.has(route)) throw new Error(`duplicate route: ${route}`);
      for (const method of ['title','module','render','mount','unmount']) if (!(method in page)) throw new Error(`${route} missing ${method}`);
      this.pages.set(route, page);
    },
    escape(value) { const node=document.createElement('div'); node.textContent=String(value ?? ''); return node.innerHTML; },
    trace(id) { return `../merged-platform-blueprint/api-atlas.html#${encodeURIComponent(id)}`; },
    toast(message) { this.setState({ toast:message }); window.setTimeout(() => this.setState({ toast:null }), 2400); },
  };
})();
