import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {renderLayout} from '../frontend/ui.js';
import {translations} from '../frontend/i18n.js';
import {uiTranslations} from '../frontend/ui-i18n.js';
import {resilienceMessages} from '../frontend/resilience-i18n.js';
const data=JSON.parse(fs.readFileSync(new URL('../frontend/demo-map.json',import.meta.url)));
function context(permissions=[],extra={}){
 const words={...translations.en,...uiTranslations.en};
 return {state:{...structuredClone(data),server_time:1,viewer:{},teams:[],alerts:[],incidents:[]},user:{role:'citizen'},health:{demo:true},view:'citizen',connection:'live',route:null,origin:{lat:40.37,lng:49.8385},pending:[],mode:'local',lang:'en',ui:{drawer:true,panel:'incidents',search:'',filter:'all',selected:null,dialog:null,layers:{shelters:true,incidents:true,teams:true,zones:false},zoom:1,pan:{x:0,y:0}},adminData:null,t:k=>words[k]||k,esc:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),icon:n=>`<svg class="icon" aria-hidden="true"></svg>`,can:p=>permissions.includes(p),fmtTime:()=> '12:00',...extra};
}
test('citizen output exposes no operational road controls and no private incident positions',()=>{
 const c=context();c.state.incidents=[{id:'i1',type:'fire',zone:'west',count:4,active_count:4}];
 const html=renderLayout(c);
 assert.ok(html.includes('data-action="sos"'));
 assert.ok(!html.includes('data-action="edit-roads"'));
 assert.ok(!html.includes('data-select="incident" data-id="i1" tabindex'));
 assert.ok(!html.includes('data-action="lab"'));
});
test('expired alerts are neutral; active capacity alerts remain critical',()=>{
 const c=context(['dashboard:read','incident:act'],{view:'dispatcher'});c.ui.panel='alerts';
 c.state.alerts=[{id:'old',kind:'sos',target:'i',created:1,evidence:{count:4,rule:'zone',zone:'west'},condition_active:false,status:'responding'},{id:'now',kind:'capacity',target:'s1',created:2,evidence:{percent:96},condition_active:true,status:'open'}];
 const html=renderLayout(c);
 assert.ok(html.includes('alert-card is-archived'));
 assert.ok(html.includes('Trigger is no longer active'));
 assert.ok(html.includes('data-alert="now" data-command="dispatch"'));
 assert.ok(html.indexOf('data-alert="now"')<html.indexOf('data-alert="old"'));
});
test('road editing retains the interactive map, but mutation lives only in details',()=>{
 const c=context(['road:write'],{view:'dispatcher'});c.ui.editRoads=true;
 let html=renderLayout(c);assert.ok(html.includes('id="city-map"'));assert.ok(!html.includes('data-road='));
 c.ui.selected={kind:'road',id:c.state.roads[0].id};html=renderLayout(c);
 assert.ok(html.includes('data-road="'+c.state.roads[0].id+'"'));
 assert.ok(html.includes('This change immediately affects citizen routes.'));
});
test('search escapes arbitrary input and produces a distinct empty state',()=>{
 const c=context();c.ui.search='<img src=x onerror=alert(1)>';
 const html=renderLayout(c);assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('<img'));assert.ok(html.includes('No matching results'));
});
test('offline shell includes every module used by the redesigned workspace',()=>{
 const sw=fs.readFileSync(new URL('../frontend/sw.js',import.meta.url),'utf8');
 for(const file of ['ui.js','ui-i18n.js','map.js','fonts.css','product-theme.css','product-ui.js'])assert.ok(sw.includes(`'/${file}'`));
 for(const locale of ['az','en','ru'])assert.deepEqual(Object.keys(uiTranslations[locale]).sort(),Object.keys(uiTranslations.en).sort());
});
test('fallback remains visible with the drawer closed in all three languages',()=>{
 for(const locale of ['az','en','ru']){
  const words={...translations[locale],...uiTranslations[locale],...resilienceMessages[locale]};
  const c=context([],{lang:locale,routing:{mode:'fallback'},t:k=>words[k]||k});
  c.ui.drawer=false;c.ui.mapStatus='fallback';
  const html=renderLayout(c);
  assert.ok(html.includes('resilience-banner '));
  assert.ok(html.includes('aria-live="polite"'));
  assert.ok(html.includes(words.routeFallback));
  assert.ok(html.includes(words.mapFallback));
  assert.deepEqual(Object.keys(resilienceMessages[locale]).sort(),Object.keys(resilienceMessages.en).sort());
 }
});
test('priority citizen has a visible role control and accessible no-route message',()=>{
 const c=context([], {user:{role:'priority_citizen',accessible_required:true}});
 c.t=k=>resilienceMessages.en[k]||uiTranslations.en[k]||translations.en[k]||k;
 c.ui.drawer=false;c.ui.dialog='login';
 const html=renderLayout(c);
 assert.ok(html.includes('data-priority-mode="off"'));
 assert.ok(html.includes('No verified accessible route'));
 assert.ok(html.includes('Accessible routes only'));
 assert.ok(html.includes('data-action="profile"'));
 assert.ok(!html.includes('data-action="edit-roads"'));
});
test('Priority 1 incident precedes a larger ordinary incident',()=>{
 const c=context(['dashboard:read'],{view:'dispatcher'});
 c.t=k=>resilienceMessages.en[k]||uiTranslations.en[k]||translations.en[k]||k;
 c.state.incidents=[{id:'ordinary',type:'fire',zone:'west',count:10,active_count:10,priority:2},{id:'priority',type:'medical',zone:'east',count:1,active_count:1,priority:1}];
 const html=renderLayout(c);
 assert.ok(html.indexOf('data-id="priority"')<html.indexOf('data-id="ordinary"'));
 assert.ok(html.includes('Critical · Priority 1'));
});
test('mass gatherings: dispatcher forecast, reserve action and citizen nearby warning',async()=>{
 const {eventMessages}=await import('../frontend/events-i18n.js');
 const words={...translations.en,...uiTranslations.en,...eventMessages.en};
 const ev={id:'ev1',name:'Cup <final>',kind:'football',node:'n6_4',lat:40.38,lng:49.842,attendance:12000,start:0,end:7200,phase:'live',presence:1,on_site:12000,seekers:720,worst:97,deficit:94,unplaced:0,reserve:{id:'s5',name:'Reserve',capacity:500,meters:600,direction:'E',absorbs:94},reserves:[{id:'s5',name:'Reserve',capacity:500,meters:600,direction:'E',absorbs:94}],uncovered:0,description:'League match with a fan zone',risks:['crush','medical'],risk:'high',
  shelters:[{id:'s2',name:'North Stadium',meters:296,incoming:561,current_percent:41,potential_percent:97.1,level:'reroute'}]};
 const d=context(['dashboard:read','incident:act','shelter:write'],{view:'dispatcher',t:k=>words[k]||k});
 d.state.events=[ev];d.ui.panel='events';
 let html=renderLayout(d);
 assert.ok(html.includes('data-select="event" data-id="ev1"'));
 assert.ok(html.includes('id="event-form"'));
 assert.ok(html.includes('Cup &lt;final&gt;') && !html.includes('Cup <final>'));
 d.ui.selected={kind:'event',id:'ev1'};html=renderLayout(d);
 assert.ok(html.includes('data-event-prepare="ev1"'));
 assert.ok(html.includes('97%') && html.includes('Rerouting stops'));
 assert.ok(html.includes('nothing has happened'));
 assert.ok(html.includes('League match with a fan zone') && html.includes('Crowd crush'));
 assert.ok(html.includes('East of the venue, 600 m on foot. Capacity 500, will take 94 people.'));
 assert.ok(html.includes('href="tel:112"') && html.includes('href="tel:103"'));
 const c=context([],{t:k=>words[k]||k,origin:{lat:40.379,lng:49.842}});c.state.events=[ev];
 html=renderLayout(c);
 assert.ok(html.includes('Mass gathering nearby') && html.includes('href="tel:112"'));
 assert.ok(!html.includes('data-event-prepare'));
 c.origin={lat:40.365,lng:49.828};
 assert.ok(!renderLayout(c).includes('Mass gathering nearby'));
});
test('earthquake warning asks citizens for status; dispatch sees responses and heat legend',async()=>{
 const {seismicMessages,heatColor}=await import('../frontend/seismic-i18n.js');
 const words={...translations.en,...uiTranslations.en,...seismicMessages.en};
 const c=context(['sos:own'],{t:k=>words[k]||k});
 c.state.seismic=[{id:'q1',created:1,devices:3,needed:3,peak:8,test:false,my_status:null}];
 let html=renderLayout(c);
 assert.ok(html.includes('EARTHQUAKE WARNING') && html.includes('Are you OK?'));
 for(const s of ['safe','need_help','trapped'])assert.ok(html.includes(`data-checkin="${s}" data-alert-id="q1"`));
 c.state.seismic[0].my_status='trapped';html=renderLayout(c);
 assert.ok(html.includes('Your answer is recorded') && html.includes('sent to dispatch as SOS'));
 const d=context(['dashboard:read','demo:write'],{view:'dispatcher',t:k=>words[k]||k,health:{demo:true,public_url:'https://10.0.0.5:3000'}});
 d.state.seismic=[{id:'q1',created:1,devices:3,needed:3,peak:8,test:false,checkins:{safe:5,need_help:2,trapped:1},help_points:[]}];
 d.state.alerts=[{id:'q1',kind:'seismic',target:'r',created:1,status:'open',condition_active:true,evidence:{devices:3,needed:3,labels:['A','B','C'],peak:8,spread_seconds:1.5,test:false}}];
 d.state.sensors=[{id:'x',label:'Phone A',level:2.4,last_seen:1}];
 d.ui.panel='alerts';d.ui.legend=true;d.ui.layers.heat=true;d.ui.dialog='lab';
 html=renderLayout(d);
 assert.ok(html.includes('I am trapped') && html.includes('>5<') && html.includes('Phone A'));
 assert.ok(!html.includes('data-checkin='));
 assert.ok(html.includes('https://10.0.0.5:3000/sensor') && html.includes('data-seismic="3"'));
 assert.ok(html.includes('Assembly point occupancy'));
 assert.equal(heatColor(0),'#2d936f');assert.equal(heatColor(150),'#d63c2c');
 assert.match(heatColor(80),/^#[0-9a-f]{6}$/);
});
