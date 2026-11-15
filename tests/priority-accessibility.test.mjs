import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {localRoutes,accessible} from '../frontend/offline.js';
import {resolveRoute} from '../frontend/routing-client.js';
const data=JSON.parse(fs.readFileSync(new URL('../frontend/demo-map.json',import.meta.url)));
const origin={lat:40.37,lng:49.8385};
function state(){return {...structuredClone(data),viewer:{role:'priority_citizen',accessible_required:true}};}
test('offline priority route uses only verified edges and shelters',()=>{
 const s=state(),routes=localRoutes(s,origin);assert.ok(routes.length);
 for(const r of routes){assert.equal(r.accessible,true);assert.ok(accessible(s.shelters.find(x=>x.id===r.shelter_id)));assert.ok(r.edges.every(id=>accessible(s.roads.find(x=>x.id===id))));}
});
test('503 and timeout preserve accessibility in browser fallback',async()=>{
 for(const request of [()=>Promise.reject({status:503}),()=>new Promise(()=>{})]){
  const s=state(),result=await resolveRoute({request,getState:()=>s,origin,timeoutMs:10});
  assert.ok(result.routes.length);assert.ok(result.routing.accessible_required);assert.ok(result.routes.every(r=>r.accessible));
 }
});
test('unknown, blocked and incomplete metadata fail closed',()=>{
 for(const key of ['accessibility_verified','step_free','ramp_access','obstacle_free','wheelchair_accessible','medical_vehicle_accessible']){
  const s=state();s.roads.forEach(r=>delete r[key]);assert.deepEqual(localRoutes(s,origin),[]);
 }
 const s=state();s.roads.forEach(r=>r.blocked=true);assert.deepEqual(localRoutes(s,origin),[]);
});
test('unverified origin connector and full accessible shelters have no route',()=>{
 const s=state();assert.deepEqual(localRoutes(s,{...origin,lat:40.3701}),[]);
 s.shelters.filter(accessible).forEach(x=>x.occupancy=x.capacity);assert.deepEqual(localRoutes(s,origin),[]);
});
test('missing cached access metadata never yields an ordinary route',async()=>{
 const s=state();s.roads.forEach(r=>delete r.step_free);
 const result=await resolveRoute({request:()=>Promise.reject({status:503}),getState:()=>s,origin});
 assert.deepEqual(result.routes,[]);assert.ok(result.no_route);
});
