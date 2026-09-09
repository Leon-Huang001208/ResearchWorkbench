(function () {
  'use strict';
  window.AlphaData = {
    async request(path,{fallback=null,timeoutMs=1800}={}) {
      const controller=new AbortController(); const timer=window.setTimeout(()=>controller.abort(),timeoutMs);
      try {
        const response=await fetch(path,{headers:{Accept:'application/json'},signal:controller.signal});
        if(!response.ok) throw new Error(`HTTP ${response.status}`);
        return {mode:'live',value:await response.json(),error:null,label:'实时数据'};
      } catch(error) {
        return {mode:'demo',value:fallback,error:String(error),label:'演示状态'};
      } finally { window.clearTimeout(timer); }
    },
    demo(value){ return {mode:'demo',value,error:null,label:'演示状态'}; },
  };
})();
