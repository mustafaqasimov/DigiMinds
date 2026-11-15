// All geometry is bundled and synthetic: the map works without a tile provider.
export function projection(lng, lat) {
  return {x: 80 + (lng - 49.828) / .0035 * 102, y: 660 - (lat - 40.365) / .0025 * 85};
}
export function mapView(ui) {
  const w = 1000 / ui.zoom, h = 760 / ui.zoom;
  return `${500 + ui.pan.x - w / 2} ${380 + ui.pan.y - h / 2} ${w} ${h}`;
}
export function renderMap({state, ui, route, origin, isCitizen, t, esc, icon}) {
  const nodes = state.map.nodes, lookup = Object.fromEntries(nodes.map(n => [n.id, n]));
  let blocks = '';
  for (let r = 0; r < 6; r++) for (let c = 0; c < 8; c++) {
    const x = 91 + c * 102, y = 164 + r * 85;
    if ((c === 4 && r === 2) || (c === 6 && r === 4) || (c === 4 && r === 0)) continue;
    blocks += `<g fill="${(r + c) % 3 ? '#e5e6df' : '#e0e3d9'}" stroke="#d6d9cf" stroke-width=".6"><rect x="${x}" y="${y}" width="35" height="24" rx="2"/><rect x="${x+47}" y="${y+3}" width="31" height="43" rx="2"/><rect x="${x+3}" y="${y+34}" width="32" height="27" rx="2"/><rect x="${x+49}" y="${y+52}" width="26" height="12" rx="2"/></g>`;
  }
  const park = (x, y, w, h) => `<g><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="#c7d9bb" stroke="#bdd0b0"/><path d="M${x+8} ${y+h-8}L${x+w-8} ${y+8}M${x+8} ${y+8}L${x+w-8} ${y+h-8}" stroke="#e5eddd" stroke-width="4"/>${[12,32,52].map((v,i)=>`<circle cx="${x+v}" cy="${y+12+i%2*30}" r="7" fill="#aec89e" opacity=".7"/>`).join('')}</g>`;
  const roads = state.roads.map(r => {
    const a=lookup[r.a], b=lookup[r.b], d=`M${a.x} ${a.y}L${b.x} ${b.y}`;
    const selected=ui.selected?.kind==='road' && ui.selected.id===r.id;
    return `<path d="${d}" stroke="#d7dacd" stroke-width="13"/><path d="${d}" stroke="#fffefa" stroke-width="10"/>${r.blocked?`<path d="${d}" stroke="#df5847" stroke-width="7" stroke-dasharray="7 5"/>`:''}${selected?`<path d="${d}" stroke="#eb8741" stroke-width="18" opacity=".3"/>`:''}${ui.editRoads?`<rect class="road-hit" data-select="road" data-id="${r.id}" x="${Math.min(a.x,b.x)-9}" y="${Math.min(a.y,b.y)-9}" width="${Math.abs(a.x-b.x)+18}" height="${Math.abs(a.y-b.y)+18}" rx="5" role="button" tabindex="0" aria-label="${esc(r.name)} · ${t(r.blocked?'closed':'open')}"/>`:''}`;
  }).join('');
  const routePath = isCitizen && route?.geometry?.map((p,i)=> {const q=projection(...p);return `${i?'L':'M'}${q.x} ${q.y}`;}).join(' ');
  function marker(kind, id, p, color, glyph, label, sub, selected) {
    return `<g class="map-marker ${selected?'is-selected':''}" data-select="${kind}" data-id="${esc(id)}" tabindex="0" role="button" aria-label="${esc(label)}${sub?' · '+esc(sub):''}"><circle cx="${p.x}" cy="${p.y}" r="29" fill="${color}" opacity="${selected?'.19':'.08'}"/>${selected?`<circle cx="${p.x}" cy="${p.y}" r="30" fill="none" stroke="${color}" stroke-width="1.5" stroke-dasharray="3 3"/>`:''}<circle cx="${p.x}" cy="${p.y}" r="18" fill="${color}" stroke="white" stroke-width="3" filter="url(#pin-shadow)"/><g transform="translate(${p.x-9} ${p.y-9})" color="white">${icon(glyph).replace('class="icon"','class="map-pin-icon" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"')}</g>${sub?`<rect x="${p.x-27}" y="${p.y+23}" width="54" height="21" rx="6" fill="white" stroke="#e0e3dc"/><text x="${p.x}" y="${p.y+37}" text-anchor="middle" class="marker-caption" fill="${color}">${esc(sub)}</text>`:''}<title>${esc(label)}</title></g>`;
  }
  const shelters = ui.layers.shelters ? state.shelters.map(s=>marker('shelter',s.id,lookup[s.node],s.status!=='open'?'#89958a':s.percent>95?'#d64d3c':s.percent>=90?'#ba780d':'#278264','home',s.name,s.status==='standby'?t('standby'):Math.round(s.percent)+'%',ui.selected?.id===s.id)).join('') : '';
  const incidents=ui.layers.incidents ? (state.incidents||[]).filter(i=>i.lat&&i.status!=='resolved'&&(i.active_count>0||ui.selected?.id===i.id)).map(i=>{
    const p=projection(i.lng,i.lat), color=i.active_count?'#db523f':'#798279';
    return `<circle cx="${p.x}" cy="${p.y}" r="51" fill="${color}" opacity=".09"/><circle cx="${p.x}" cy="${p.y}" r="51" fill="none" stroke="${color}" opacity=".35" stroke-dasharray="4 5"/>${marker('incident',i.id,p,color,i.type,t(i.type),i.count+' SOS',ui.selected?.id===i.id)}`;
  }).join('') : '';
  const teams=ui.layers.teams&&!isCitizen ? (state.teams||[]).map(team=>marker('team',team.id,lookup[team.node],team.status==='available'?'#557795':'#3e68c0','team',team.name,'',ui.selected?.id===team.id)).join('') : '';
  const citizen=projection(origin.lng,origin.lat);
  return `<svg id="city-map" class="map-svg" viewBox="${mapView(ui)}" aria-label="${t('mapTitle')}. ${t('keyboardMap')}" tabindex="0"><defs><pattern id="grain" width="8" height="8" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r=".5" fill="#a2b099" opacity=".16"/></pattern><filter id="pin-shadow" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity=".18"/></filter></defs><rect x="-1500" y="-1000" width="4000" height="3000" fill="#eff0e8"/><rect x="-1500" y="-1000" width="4000" height="3000" fill="url(#grain)"/><path d="M-100 715Q90 675 300 714T710 704Q940 675 1100 750V1800H-100Z" fill="#c5dee1"/><path d="M-100 699Q90 659 300 698T710 688Q940 659 1100 734" fill="none" stroke="#d4dfc6" stroke-width="16"/><path d="M-100 698Q90 658 300 697T710 687Q940 658 1100 733" fill="none" stroke="#fafbf2" stroke-width="4"/>
  ${ui.layers.zones?'<path d="M49 117H489V685H49Z" fill="#a8c292" opacity=".13" stroke="#759766" stroke-dasharray="7 6"/><path d="M493 117H927V685H493Z" fill="#e7cfaa" opacity=".19" stroke="#bb9562" stroke-dasharray="7 6"/>':''}
  ${blocks}${park(499,333,80,65)}${park(703,505,85,57)}${park(499,164,80,65)}${roads}
  <g class="district-label"><text x="230" y="111" text-anchor="middle">${t('west')}</text><text x="745" y="111" text-anchor="middle">${t('east')}</text><text x="294" y="442" text-anchor="middle" class="city-label">${t('cityLabel')}</text><text x="535" y="373" class="park-label" text-anchor="middle">${t('centerPark')}</text><text x="750" y="744" text-anchor="middle">${t('waterfront')}</text></g>
  ${routePath?`<path d="${routePath}" fill="none" stroke="white" stroke-width="12" stroke-linejoin="round"/><path class="route-line" d="${routePath}" fill="none" stroke="#3a6cda" stroke-width="6" stroke-linejoin="round"/><path d="${routePath}" fill="none" stroke="#b9d0ff" stroke-width="1.5" stroke-dasharray="3 12"/>`:''}
  ${isCitizen&&ui.chooseLocation?nodes.map(n=>`<circle class="node-hit" data-node="${n.id}" cx="${n.x}" cy="${n.y}" r="13" role="button" tabindex="0" aria-label="${n.lat.toFixed(4)}, ${n.lng.toFixed(4)}"/>`).join(''):''}
  ${shelters}${teams}${incidents}
  ${isCitizen?`<g class="you-marker"><circle cx="${citizen.x}" cy="${citizen.y}" r="27" fill="#356cd4" opacity=".13"/><circle cx="${citizen.x}" cy="${citizen.y}" r="10" fill="#356cd4" stroke="white" stroke-width="4"/><rect x="${citizen.x-56}" y="${citizen.y+21}" width="112" height="23" rx="6" fill="#263a4b"/><text x="${citizen.x}" y="${citizen.y+37}" text-anchor="middle" fill="white" class="marker-caption">${t('currentLocation')}</text></g>`:''}</svg>`;
}
