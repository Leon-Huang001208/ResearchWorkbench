/** Decode JSON before checking provider reflection. Never log or return matched secrets. */
export function safeModelText(text,secrets){
  if(typeof text!=='string'||secrets.size===0)return false;
  const reflects=value=>[...secrets].some(secret=>typeof secret==='string'&&secret.length>0&&value.includes(secret));
  if(reflects(text))return false;
  function scan(value,depth=0){
    if(depth>64)return false;
    if(typeof value==='string')return !reflects(value);
    if(Array.isArray(value))return value.every(part=>scan(part,depth+1));
    if(value&&typeof value==='object')return Object.entries(value).every(([key,part])=>!reflects(key)&&scan(part,depth+1));
    return true;
  }
  try{return scan(JSON.parse(text));}catch{return true;}
}
