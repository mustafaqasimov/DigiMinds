import {localRoutes} from './offline.js';

function fallback(getState,origin,reason){
 try{return {routes:localRoutes(getState(),origin),routing:{mode:'fallback',reason,source:'browser_offline'},fallback_reason:reason};}
 catch(error){return {routes:[],routing:{mode:'fallback',reason,source:'browser_offline'},fallback_reason:reason,local_error:error.message==='outside_demo_area'?'outside_demo_area':'local_data_unavailable',no_route:true};}
}
// The deadline covers both fetch and JSON parsing. A rejected fallback never leaks.
export async function resolveRoute({request,getState,origin,mode='auto',online=true,timeoutMs=5000}){
 if(!online)return fallback(getState,origin,'browser_offline');
 const controller=new AbortController();let timer;
 try{
  const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Object.assign(Error('route_api_timeout'),{network:true}));},timeoutMs);});
  const result=await Promise.race([request(`/routes?lat=${origin.lat}&lng=${origin.lng}&mode=${mode}`,{signal:controller.signal}),deadline]);
  if(!result||!Array.isArray(result.routes))throw Object.assign(Error('invalid_route_response'),{network:true});
  return {...result,routing:result.routing||{mode:mode==='local'?'local':'online',reason:result.fallback_reason}};
 }catch(error){
  if(error.network||error.status>=500||error.status===408)return fallback(getState,origin,error.status?'route_api_http_'+error.status:error.message);
  throw error; // Authentication, validation and rate limits retain their semantics.
 }finally{clearTimeout(timer);}
}
