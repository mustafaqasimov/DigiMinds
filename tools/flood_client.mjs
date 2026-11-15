// Real HTTP burst driver. Fixture credentials arrive on stdin and are never logged.
import http from 'node:http';
import {performance} from 'node:perf_hooks';

let input='';for await(const chunk of process.stdin)input+=chunk;
const config=JSON.parse(input),agent=new http.Agent({keepAlive:true,maxSockets:config.requests+40,maxFreeSockets:config.requests+40});
const samples=[],statuses={};
function request(path,token,payload,group){
 const started=performance.now(),data=payload===undefined?null:JSON.stringify(payload);
 return new Promise((resolve,reject)=>{
  const req=http.request(new URL(path,config.base_url),{agent,method:data===null?'GET':'POST',headers:{...(token?{Authorization:'Bearer '+token}:{}),...(data===null?{}:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)})}},res=>{
   let text='';res.on('data',chunk=>text+=chunk);res.on('end',()=>{
    const result={status:res.statusCode,ms:performance.now()-started,headers:res.headers,body:JSON.parse(text)};
    const timing=/dur=([\d.]+)/.exec(res.headers['server-timing']||'');
    if(group){samples.push({group,ms:result.ms,status:result.status,server_ms:timing?Number(timing[1]):null});statuses[result.status]=(statuses[result.status]||0)+1;}
    resolve(result);
   });
  });
  req.setTimeout(10000,()=>req.destroy(new Error('HTTP timeout')));req.on('error',reject);
  req.end(data);
 });
}
function stats(values){
 const sorted=[...values].sort((a,b)=>a-b),round=x=>Math.round(x*100)/100;
 return {count:sorted.length,mean_ms:round(sorted.reduce((a,b)=>a+b,0)/sorted.length),p95_ms:round(sorted[Math.ceil(sorted.length*.95)-1]),max_ms:round(sorted.at(-1))};
}
try{
 if(config.warm)await Promise.all(Array.from({length:config.requests+30},()=>request('/api/health')));
 const start=performance.now(),pending=[];
 for(let i=0;i<config.requests;i++){
  const index=config.scenario==='replay'?0:i%config.tokens.length;
  const token=config.scenario==='invalid'?'invalid-jwt-'+i:config.tokens[index];
  const payload={...config.payload,event_key:config.scenario==='replay'?config.payload.event_key:'flood-event-'+i};
  pending.push(request('/api/sos',token,payload,'sos'));
  if(i===Math.floor(config.requests/2)){
   // Operator work is launched while hundreds of SOS requests are outstanding.
   for(let j=0;j<10;j++)pending.push(request('/api/state',config.operator,undefined,'dashboard'));
   for(let j=0;j<10;j++)pending.push(request('/api/alerts/'+config.alert+'/dispatch',config.operator,{},'dispatch'));
   if(config.scenario==='replay')pending.push(request('/api/sos',config.genuine,{...config.payload,type:'medical',event_key:'genuine-under-flood'},'genuine'));
  }
 }
 const results=await Promise.all(pending),elapsed=performance.now()-start;
 const byGroup=Object.fromEntries(['sos','dashboard','dispatch','genuine'].map(group=>[group,samples.filter(s=>s.group===group)]).filter(([,s])=>s.length).map(([g,s])=>[g,stats(s.map(x=>x.ms))]));
 const accepted=samples.filter(s=>s.group==='sos'&&s.status<300),blocked=samples.filter(s=>s.group==='sos'&&s.status>=400);
 const operatorOk=samples.filter(s=>['dashboard','dispatch'].includes(s.group)).every(s=>s.status===200);
 const genuineOk=samples.filter(s=>s.group==='genuine').every(s=>s.status===201);
 const retryOk=results.filter(r=>r.status===429).every(r=>Number(r.headers['retry-after'])>=1);
 const badStatus=samples.some(s=>s.group==='sos'&&![200,201,401,429].includes(s.status));
 console.log(JSON.stringify({scenario:config.scenario,connections:config.warm?'warm_keep_alive':'cold_tcp',requests:config.requests,concurrency:config.requests,
  elapsed_ms:Math.round(elapsed*100)/100,http_statuses:statuses,groups:byGroup,
  server_groups:Object.fromEntries(Object.keys(byGroup).map(g=>[g,stats(samples.filter(s=>s.group===g&&s.server_ms!==null).map(s=>s.server_ms))])),
  ...(accepted.length?{accepted_sos:stats(accepted.map(s=>s.ms))}:{}),...(blocked.length?{blocked_sos:stats(blocked.map(s=>s.ms))}:{}),
  operator_ok:operatorOk,genuine_ok:genuineOk,retry_after_ok:retryOk,unexpected_status:badStatus,
  created:results.filter(r=>r.status===201).length,
  latency_pass:Object.values(byGroup).every(g=>g.mean_ms<300)&&(!accepted.length||stats(accepted.map(s=>s.ms)).mean_ms<300),
  functionality_pass:operatorOk&&genuineOk&&retryOk&&!badStatus}));
}finally{agent.destroy();}
