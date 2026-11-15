import {addBase} from './map-base.js';
const header=document.getElementById('site-header');
function headerState(){header.classList.toggle('scrolled',scrollY>40);}headerState();window.addEventListener('scroll',headerState,{passive:true});
document.getElementById('mobile-toggle').addEventListener('click',event=>{const open=header.classList.toggle('menu-open');event.currentTarget.setAttribute('aria-expanded',String(open));});
document.querySelectorAll('.primary-nav a').forEach(a=>a.addEventListener('click',()=>{header.classList.remove('menu-open');document.getElementById('mobile-toggle').setAttribute('aria-expanded','false');document.querySelectorAll('details.nav-dropdown').forEach(d=>d.open=false);}));
document.addEventListener('click',event=>{if(!event.target.closest('.nav-dropdown'))document.querySelectorAll('.nav-dropdown').forEach(d=>d.open=false);});
document.addEventListener('keydown',event=>{if(event.key==='Escape'){document.querySelectorAll('.nav-dropdown').forEach(d=>d.open=false);header.classList.remove('menu-open');document.getElementById('mobile-toggle').setAttribute('aria-expanded','false');}});
function preview(element){
 const L=window.L;if(!L)return;
 const type=element.dataset.map;
 const map=L.map(element,{zoomControl:false,attributionControl:true,scrollWheelZoom:false,dragging:false,touchZoom:false,doubleClickZoom:false,boxZoom:false,keyboard:false}).setView(type==='phone'?[40.371,49.844]:[40.375,49.848],type==='phone'?14:15);
 addBase(map,{offline:type==='offline'});
 const pin=(lat,lng,color,glyph)=>L.marker([lat,lng],{interactive:false,icon:L.divIcon({className:'landing-pin',html:`<span class="pin-disc ${color}">${glyph}</span>`,iconSize:[37,37],iconAnchor:[18,18]})}).addTo(map);
 if(type==='cases'){L.polygon([[40.381,49.858],[40.375,49.851],[40.368,49.841],[40.362,49.842],[40.372,49.859],[40.381,49.867]],{color:'#348ce1',weight:2,fillColor:'#5caeff',fillOpacity:.2,interactive:false}).addTo(map);pin(40.369,49.847,'blue','≋');}
 else{L.polygon([[40.379,49.835],[40.382,49.849],[40.377,49.854],[40.371,49.847],[40.371,49.838]],{color:'#d98a34',weight:1.5,fillColor:'#ffca57',fillOpacity:.17,dashArray:'5 5',interactive:false}).addTo(map);pin(40.378,49.842,'','♨');pin(40.3696,49.8418,'green','⌂');pin(40.375,49.856,'green','⌂');pin(40.384,49.849,'blue','+');}
}
const observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){preview(entry.target);observer.unobserve(entry.target);}},{rootMargin:'0px'});
window.addEventListener('load',()=>document.querySelectorAll('[data-map]').forEach(el=>observer.observe(el)));
if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
