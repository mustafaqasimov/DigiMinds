import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {localRoutes} from '../frontend/offline.js';
const fresh=()=>JSON.parse(fs.readFileSync(new URL('../frontend/demo-map.json',import.meta.url)));
const origin={lat:40.37,lng:49.8385};
test('browser routes avoid closed edges and choose a different shelter at 90%',()=>{
 const state=fresh(),before=localRoutes(state,origin)[0];
 const edge=before.edges[0];state.roads.find(r=>r.id===edge).blocked=true;
 const changed=localRoutes(state,origin);
 assert.ok(changed.length);assert.ok(changed.every(r=>!r.edges.includes(edge)));
 const shelter=state.shelters.find(s=>s.id===before.shelter_id);shelter.occupancy=shelter.capacity*.9;
 assert.ok(localRoutes(state,origin).every(r=>r.shelter_id!==shelter.id));
});
test('disconnected browser graph does not invent a straight-line route',()=>{
 const state=fresh();state.roads.forEach(r=>r.blocked=true);
 assert.deepEqual(localRoutes(state,origin),[]);
});
test('out of covered area is explicit and offline data is marked stale',()=>{
 assert.throws(()=>localRoutes(fresh(),{lat:41,lng:50}),/outside_demo_area/);
 assert.ok(localRoutes(fresh(),origin).every(r=>r.stale&&r.source==='browser_offline'));
});
