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
