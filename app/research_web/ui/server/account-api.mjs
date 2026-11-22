/** Same-origin account API. Never logs credentials or response bodies. */
const messages = {
  invalid_credentials:'账号或密码不正确。', login_rate_limited:'登录尝试过多，请稍后再试。',
  username_exists:'这个账号已存在。', invalid_username:'账号需为3—64位字母、数字、下划线、点或短横线，并以字母开头。',
  invalid_password:'密码至少需要12个字符。', last_active_admin:'不能停用最后一个管理员。',
  primary_account_protected:'原常驻实例由原监督器管理，不能在此停止或停用。',
  login_required:'登录已过期，请重新登录。', forbidden:'没有管理用户的权限。',
};
export function createAccountAPI({fetcher=globalThis.fetch?.bind(globalThis), redirect=url=>globalThis.location.assign(url), logger=()=>{}, timeout=15000}={}) {
  return async function request(path, method='GET', body) {
    const abort=new AbortController(); const timer=setTimeout(()=>abort.abort(),timeout);
    try {
      const response=await fetcher(`/api/server/${path}`,{method,credentials:'same-origin',signal:abort.signal,...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
      if(response.status===401&&path!=='login') {redirect('/auth');throw Object.assign(Error(messages.login_required),{code:'login_required',status:401});}
      let value;
      try {value=await response.json();} catch {throw Object.assign(Error('服务器返回异常，请稍后重试。'),{code:'account_response_invalid'});}
      if(!response.ok) {
        const code=response.status===401&&path!=='login'?'login_required':response.status===403?'forbidden':value?.error?.code;
        throw Object.assign(Error(messages[code]||'操作未完成，请检查输入或稍后重试。'),{code:messages[code]?code:'account_request_failed',status:response.status});
      }
      return value;
    } catch(error) {
      logger('account_request_failed',{status:error.status||0});
      if(error.code)throw error;
      throw Object.assign(Error('网络请求未完成，请检查网络后重试。'),{code:'account_network_failed'});
    } finally {clearTimeout(timer);}
  };
}

export function legacyAccountTarget(pathname, hash='') {
  return pathname==='/account'||/^#\/settings\/account(?:\?|$)/.test(hash)?'/#/account':null;
}
