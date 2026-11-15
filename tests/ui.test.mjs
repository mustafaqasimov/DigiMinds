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
test('mass gatherings: dispatcher forecast, reserve action and citizen nearby warning',async()=>{
 const {eventMessages}=await import('../frontend/events-i18n.js');
 const words={...translations.en,...uiTranslations.en,...eventMessages.en};
 const ev={id:'ev1',name:'Cup <final>',kind:'football',node:'n6_4',lat:40.38,lng:49.842,attendance:12000,start:0,end:7200,phase:'live',presence:1,on_site:12000,seekers:720,worst:97,deficit:94,unplaced:0,reserve:{id:'s5',name:'Reserve',capacity:500,meters:600},
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
 const c=context([],{t:k=>words[k]||k,origin:{lat:40.379,lng:49.842}});c.state.events=[ev];
 html=renderLayout(c);
 assert.ok(html.includes('Mass gathering nearby'));
 assert.ok(!html.includes('data-event-prepare'));
 c.origin={lat:40.365,lng:49.828};
 assert.ok(!renderLayout(c).includes('Mass gathering nearby'));
});
