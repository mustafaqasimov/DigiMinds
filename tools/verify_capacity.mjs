// Optional browser regression: requires Playwright and its Chromium browser.
// Creates an isolated demo server/database; never touches a live deployment.
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)('playwright');
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const dir=await mkdtemp(path.join(tmpdir(),'dm-capacity-'));
const base='http://127.0.0.1:3029';
const server=spawn(process.env.DM_PYTHON||'python',['-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','3029'],{cwd:root,env:{...process.env,DATABASE_PATH:path.join(dir,'test.db'),DEMO_MODE:'1',ORS_API_KEY:''},stdio:['ignore','pipe','pipe']});
let logs='';server.stderr.on('data',x=>logs+=x);
let browser;
try {
 for(let i=0;i<100;i++){
  if(server.exitCode!==null)throw Error(logs);
  try{if((await fetch(base+'/api/health')).ok)break;}catch{}
  await new Promise(r=>setTimeout(r,100));
 }
 browser=await chromium.launch({headless:true,...(process.env.DM_CHROMIUM?{executablePath:process.env.DM_CHROMIUM}:{})});
 const citizen=await browser.newContext({baseURL:base,viewport:{width:1440,height:1000}});
 const dispatcher=await browser.newContext({baseURL:base,viewport:{width:1440,height:1000}});
 const c=await citizen.newPage(),d=await dispatcher.newPage();
 const errors=[];c.on('pageerror',e=>errors.push(e.message));d.on('pageerror',e=>errors.push(e.message));
 const wait=async(fn)=>{for(let i=0;i<100;i++){if(await fn())return;await new Promise(r=>setTimeout(r,100));}throw Error('Browser state timed out');};
 await c.goto(base+'/workspace.html');
 await c.locator('.journey-card .destination').waitFor();
 const old=await c.locator('.journey-card .destination').getAttribute('data-id');
 assert.equal(old,'s1');
 await d.goto(base+'/workspace.html');
 await d.getByRole('button',{name:'Rol dəyiş',exact:true}).click();
 await d.locator('[data-login="dispatcher"]').click();
 await d.locator('[data-panel="shelters"]').first().click();
 await d.locator('[data-select="shelter"][data-id="s1"]').click();
 await d.locator('#occupancy-count').fill('360');
 await d.locator('#occupancy-form button[type="submit"]').click();
 await d.locator('.alert-card.is-warning').waitFor();
 assert.equal(await d.locator('[data-command="dispatch"]').count(),0);
 await wait(async()=>await c.locator('.journey-card .destination').getAttribute('data-id')!=='s1');
 const warning=await d.locator('[data-command="open_shelter"]').getAttribute('data-alert');
 await d.locator('[data-command="open_shelter"]').click();
 await d.getByText('Məntəqə açıldı:',{exact:false}).waitFor();
 let state=await (await dispatcher.request.get('/api/state')).json();
 let a=state.alerts.find(a=>a.id===warning);
 assert.ok(a.actions.open_shelter);
 assert.equal(state.shelters.find(s=>s.id===a.actions.open_shelter).status,'open');
 assert.equal(state.teams.filter(t=>t.status==='en_route').length,0);
 console.log('PASS: exact 90% reroutes a separate live citizen and opens a reserve from shelter details.');
 // End the old episode so the next critical event has a fresh confirmation.
 await d.locator('#occupancy-count').fill('240');await d.locator('#occupancy-form button').click();
 await wait(async()=>await d.locator('.alert-card').count()===0);
 await d.locator('#occupancy-count').fill('384');await d.locator('#occupancy-form button').click();
 await d.locator('[data-command="respond"]').waitFor();
 assert.ok(await d.getByText('QIRMIZI HƏYƏCAN',{exact:true}).isVisible());
 if(process.env.DM_SCREENSHOT_DIR)await d.screenshot({path:path.join(process.env.DM_SCREENSHOT_DIR,'capacity-critical.png')});
 const alert=await d.locator('[data-command="respond"]').getAttribute('data-alert');
 await d.locator('[data-command="respond"]').click();
 await d.getByText('Briqada göndərildi:',{exact:false}).waitFor();
 await d.getByText('Məntəqə açıldı:',{exact:false}).waitFor();
 state=await (await dispatcher.request.get('/api/state')).json();a=state.alerts.find(a=>a.id===alert);
 assert.deepEqual(Object.keys(a.actions).sort(),['dispatch','open_shelter']);
 assert.equal(state.teams.filter(t=>t.status==='en_route').length,1);
 const repeat=await dispatcher.request.post('/api/alerts/'+alert+'/respond',{headers:{'X-Requested-With':'DigiMinds'}});
 assert.ok((await repeat.json()).duplicate);
 assert.equal(await d.locator('[data-command="respond"]').count(),0);
 console.log('PASS: >95% red alert performs both operations once; completed resources stay visible.');
 await d.setViewportSize({width:390,height:844});
 if(process.env.DM_SCREENSHOT_DIR)await d.screenshot({path:path.join(process.env.DM_SCREENSHOT_DIR,'capacity-mobile.png')});
 assert.ok(await d.getByText('Briqada göndərildi:',{exact:false}).isVisible());
 assert.ok(await d.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 // Road closures update the route without the citizen pressing refresh.
 let route=(await (await citizen.request.get('/api/routes?lat=40.37&lng=49.8385&mode=local')).json()).routes[0];
 const edge=route.edges[0];
 const requests=[];c.on('request',r=>{if(r.url().includes('/api/routes?'))requests.push(r.url());});
 await dispatcher.request.patch('/api/roads/'+edge,{headers:{'X-Requested-With':'DigiMinds'},data:{enabled:true}});
 await wait(()=>requests.length>0);
 route=(await (await citizen.request.get('/api/routes?lat=40.37&lng=49.8385&mode=local')).json()).routes[0];
 assert.ok(!route.edges.includes(edge));
 assert.deepEqual(errors,[]);
 console.log('PASS: road closure triggers automatic route recalculation; mobile layout fits; no page JavaScript errors.');
} finally {
 await browser?.close();server.kill('SIGTERM');
 await new Promise(resolve=>{if(server.exitCode!==null)resolve();else server.once('exit',resolve);});
 await rm(dir,{recursive:true,force:true});
}
