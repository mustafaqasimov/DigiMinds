import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {resolveRoute} from '../frontend/routing-client.js';
import {MapCircuit} from '../frontend/map-circuit.js';
const state=()=>JSON.parse(fs.readFileSync(new URL('../frontend/demo-map.json',import.meta.url)));
const origin={lat:40.37,lng:49.8385};

test('API 503 falls back to current local data while Internet is still online',async()=>{
 const data=state();let route=await resolveRoute({getState:()=>data,origin,request:async()=>{throw {status:503};}});
 assert.ok(route.routes.length);assert.equal(route.routing.mode,'fallback');assert.equal(route.routing.reason,'route_api_http_503');
 const old=route.routes[0];data.shelters.find(s=>s.id===old.shelter_id).occupancy=99999;
 route=await resolveRoute({getState:()=>data,origin,request:async()=>{throw {status:503};}});
 assert.ok(route.routes.every(r=>r.shelter_id!==old.shelter_id));
});
test('hanging API is aborted; latest graph rather than stale pre-request graph is used',async()=>{
 const data=state();let aborted=false;
 const response=await resolveRoute({getState:()=>data,origin,timeoutMs:20,request:async(path,{signal})=>{
  signal.addEventListener('abort',()=>aborted=true);data.roads.forEach(r=>r.blocked=true);return new Promise(()=>{});
 }});
 assert.ok(aborted);assert.deepEqual(response.routes,[]);assert.equal(response.routing.reason,'route_api_timeout');
});
test('invalid/off-area backup returns a handled no-route result, not a rejection',async()=>{
 const result=await resolveRoute({getState:()=>state(),origin:{lat:41,lng:50},online:false});
 assert.equal(result.local_error,'outside_demo_area');assert.deepEqual(result.routes,[]);
 const missing=await resolveRoute({getState:()=>null,origin,online:false});assert.equal(missing.local_error,'local_data_unavailable');
});
test('auth and rate limit errors are not masked as successful offline requests',async()=>{
 for(const status of [401,403,422,429])await assert.rejects(()=>resolveRoute({getState:()=>state(),origin,request:async()=>{throw {status};}}),e=>e.status===status);
});
test('server fallback metadata reaches the UI unchanged',async()=>{
 const result=await resolveRoute({getState:()=>state(),origin,request:async()=>({routes:[],routing:{mode:'fallback',reason:'circuit_open',circuit:{state:'open'}}})});
 assert.equal(result.routing.circuit.state,'open');
});
test('stalled tile opens the map circuit, late tile success cannot close it',async()=>{
 let opens=0,now=0;const gate=new MapCircuit({timeoutMs:10,cooldownMs:30,clock:()=>now,onOpen:()=>opens++});
 const tile={};gate.watch(tile);await new Promise(r=>setTimeout(r,25));
 assert.equal(gate.state,'open');assert.equal(opens,1);gate.loaded(tile);assert.equal(gate.state,'open');
 assert.equal(gate.allowProbe(),false);now=31;assert.equal(gate.allowProbe(),true);assert.equal(gate.allowProbe(),false);
 gate.recovered();assert.equal(gate.state,'closed');gate.clear();
});
test('tile HTTP failure immediately opens fallback and batches duplicate errors',()=>{
 let opens=0;const gate=new MapCircuit({onOpen:()=>opens++});gate.fail('http_503');gate.fail('http_503');
 assert.equal(gate.state,'open');assert.equal(opens,1);gate.clear();
});
