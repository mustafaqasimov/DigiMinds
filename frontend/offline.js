// Independent browser routing + durable outbox; no third-party script or API.
export function distance(a,b){const rad=Math.PI/180,d1=(b.lat-a.lat)*rad,d2=(b.lng-a.lng)*rad,h=Math.sin(d1/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin(d2/2)**2;return 6371000*2*Math.asin(Math.min(1,Math.sqrt(h)));}
export function accessible(item){return ['accessibility_verified','step_free','ramp_access','obstacle_free','wheelchair_accessible','medical_vehicle_accessible'].every(key=>item[key]===true);}
export function localRoutes(state,origin,accessibleOnly=state.viewer?.accessible_required||state.viewer?.role==='priority_citizen'){
 const nodes=state.map.nodes,lookup=Object.fromEntries(nodes.map(n=>[n.id,n]));
 const start=[...nodes].sort((a,b)=>distance(a,origin)-distance(b,origin))[0];
 if(distance(start,origin)>250)throw Error('outside_demo_area');
 if(accessibleOnly&&distance(start,origin)>2)return [];
 const adj=Object.fromEntries(nodes.map(n=>[n.id,[]]));for(const r of state.roads)if(!r.blocked&&(!accessibleOnly||accessible(r))){adj[r.a].push([r.b,r.meters,r.id]);adj[r.b].push([r.a,r.meters,r.id]);}
 const cost={[start.id]:0},prev={},todo=new Set(nodes.map(n=>n.id));
 while(todo.size){let current=null,min=Infinity;for(const n of todo)if((cost[n]??Infinity)<min){min=cost[n];current=n;}if(current===null)break;todo.delete(current);for(const [n,w,id]of adj[current])if(min+w<(cost[n]??Infinity)){cost[n]=min+w;prev[n]=[current,id];}}
 return state.shelters.filter(s=>(!accessibleOnly||accessible(s))&&s.status==='open'&&s.occupancy/s.capacity*100<state.config.reroute_percent&&cost[s.node]!==undefined).map(s=>{let n=s.node,path=[n],edges=[];while(n!==start.id){const p=prev[n];edges.push(p[1]);n=p[0];path.push(n);}path.reverse();edges.reverse();return{shelter_id:s.id,shelter_name:s.name,nodes:path,edges,meters:Math.round(cost[s.node]),minutes:Math.round(cost[s.node]/75*10)/10,geometry:path.map(n=>[lookup[n].lng,lookup[n].lat]),source:'browser_offline',accessible:!!accessibleOnly,accessibility_scope:accessibleOnly?'simulation':null,stale:true};}).sort((a,b)=>a.meters-b.meters);
}
function db(){return new Promise((resolve,reject)=>{const r=indexedDB.open('digiminds',1);r.onupgradeneeded=()=>{r.result.createObjectStore('outbox',{keyPath:'event_key'});r.result.createObjectStore('cache');};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}
async function operation(store,mode,fn){const d=await db();return new Promise((resolve,reject)=>{const tx=d.transaction(store,mode),request=fn(tx.objectStore(store));let value;request.onsuccess=()=>value=request.result;tx.oncomplete=()=>{d.close();resolve(value);};tx.onerror=()=>{d.close();reject(tx.error);};});}
export const outbox={all:()=>operation('outbox','readonly',s=>s.getAll()),put:v=>operation('outbox','readwrite',s=>s.put(v)),remove:id=>operation('outbox','readwrite',s=>s.delete(id))};
export const cache={get:key=>operation('cache','readonly',s=>s.get(key)),put:(key,value)=>operation('cache','readwrite',s=>s.put(value,key))};
