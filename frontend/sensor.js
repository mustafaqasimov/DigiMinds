import {ShakeDetector, nodePosition} from './seismic.js';
const $ = s => document.querySelector(s);
const store = {get: k => {try {return localStorage.getItem(k);} catch {return null;}}, set: (k, v) => {try {localStorage.setItem(k, v);} catch {}}};
const detector = new ShakeDetector();
const samples = [];  // last 10 s of {t, value}
let last = null, rate = 0, events = 0, latest = {level: 0, ratio: 0}, pendingTrigger = null, confirmedId = null, online = false, wakeLock = null;

$('#label').value = store.get('dm_sensor_label') || 'Cihaz ' + (10 + Math.floor(Math.random() * 90));
$('#place').value = store.get('dm_sensor_place') || 'n3_4';

async function api(path, options = {}) {
  const r = await fetch('/api' + path, {...options, headers: {'Content-Type': 'application/json', 'X-Requested-With': 'DigiMinds'}, signal: AbortSignal.timeout(5000)});
  if (!r.ok) throw Object.assign(Error((await r.json().catch(() => ({}))).detail || r.statusText), {status: r.status});
  return r.json();
}

function diagnostics() {
  const secure = window.isSecureContext, supported = 'DeviceMotionEvent' in window;
  $('#diag').innerHTML = [
    ['Təhlükəsiz bağlantı (HTTPS)', secure, secure ? 'var' : 'yoxdur — telefon sensoru blok edə bilər'],
    ['Hərəkət sensoru API', supported, supported ? 'dəstəklənir' : 'dəstəklənmir'],
    ['Sensor məlumatı', rate > 0, rate > 0 ? `${rate} Hz` : 'hələ gəlmir'],
    ['Server', online, online ? 'qoşulub' : 'qoşulmayıb'],
  ].map(([name, ok, text]) => `<div>${name}: <b class="${ok ? 'ok' : 'bad'}">${text}</b></div>`).join('');
}

function setStatus(kind, title, sub) {
  const el = $('#status'); el.className = kind;
  el.innerHTML = `<b>${title}</b><small>${sub}</small>`;
}

function body(extra = {}) {
  const pos = nodePosition($('#place').value);
  return JSON.stringify({label: $('#label').value.trim() || 'Cihaz', ...pos, level: Math.min(200, latest.level), ratio: Math.min(10000, latest.ratio), ...extra});
}

async function send(extra) {
  try {
    const res = await api('/sensors/reading', {method: 'POST', body: body(extra)});
    online = true; $('#conn').textContent = 'onlayn';
    $('#m-devices').textContent = `${res.devices_online} / ${res.needed}`;
    const event = res.seismic[0];
    if (event && event.id !== confirmedId) {
      confirmedId = event.id;
      navigator.vibrate?.([400, 150, 400, 150, 800]);
    }
    if (event) setStatus('confirmed', 'ZƏLZƏLƏ XƏBƏRDARLIĞI', `Server təsdiqlədi: ${event.devices} cihaz · pik ${event.peak} m/s²`);
    else if (!detector.active) setStatus('', 'Sakit', 'Titrəmə gözlənilir · stol silkələnəndə aşkarlanacaq');
  } catch (e) {
    online = false; $('#conn').textContent = e.status === 401 ? 'sessiya yoxdur' : 'qoşulmayıb';
  }
  diagnostics();
}

function onMotion(e) {
  const now = performance.now() / 1000;
  const dt = last === null ? .016 : Math.min(.2, Math.max(.001, now - last));
  last = now; events++;
  const linear = e.acceleration && e.acceleration.x !== null;
  const a = linear ? e.acceleration : e.accelerationIncludingGravity;
  if (!a || a.x === null) return;
  const r = detector.push({x: a.x || 0, y: a.y || 0, z: a.z || 0}, dt, !linear);
  latest = r;
  samples.push({t: now, value: r.value});
  while (samples.length && samples[0].t < now - 10) samples.shift();
  if (r.onset) {
    setStatus('shake', 'TİTRƏMƏ AŞKARLANDI', 'Serverə göndərilir, digər cihazlar gözlənilir…');
    navigator.vibrate?.(120);
    // Collect the peak for ~0.8 s after onset, then report once.
    clearTimeout(pendingTrigger);
    pendingTrigger = setTimeout(() => send({triggered: true, peak: Math.min(200, detector.peak)}), 800);
  }
}

function draw() {
  const c = $('#wave'), g = c.getContext('2d'), w = c.width, h = c.height, now = performance.now() / 1000;
  g.clearRect(0, 0, w, h);
  const max = Math.max(4, ...samples.map(s => s.value)) * 1.1;
  const y = v => h - 10 - v / max * (h - 20);
  g.strokeStyle = '#e3e7df'; g.lineWidth = 2;
  for (let v = 0; v <= max; v += max > 20 ? 10 : 2) {g.beginPath(); g.moveTo(0, y(v)); g.lineTo(w, y(v)); g.stroke();}
  g.setLineDash([10, 8]); g.strokeStyle = '#d9772b';
  g.beginPath(); g.moveTo(0, y(detector.minLevel)); g.lineTo(w, y(detector.minLevel)); g.stroke(); g.setLineDash([]);
  g.strokeStyle = detector.active ? '#cc4c3a' : '#426ab3'; g.lineWidth = 3; g.beginPath();
  samples.forEach((s, i) => {const x = w - (now - s.t) / 10 * w; i ? g.lineTo(x, y(s.value)) : g.moveTo(x, y(s.value));});
  g.stroke();
  $('#m-level').textContent = latest.level.toFixed(2);
  $('#m-ratio').textContent = latest.ratio > 99 ? '99+' : latest.ratio.toFixed(1);
  requestAnimationFrame(draw);
}

$('#start').addEventListener('click', async () => {
  store.set('dm_sensor_label', $('#label').value.trim()); store.set('dm_sensor_place', $('#place').value);
  try {
    // iOS 13+ requires an explicit permission prompt from a user gesture.
    if (typeof DeviceMotionEvent?.requestPermission === 'function' && await DeviceMotionEvent.requestPermission() !== 'granted') {
      setStatus('confirmed', 'İcazə verilmədi', 'Hərəkət sensoruna icazə verin və səhifəni yeniləyin'); return;
    }
    await api('/auth/guest', {method: 'POST'});
  } catch (e) {
    setStatus('confirmed', 'Başlatmaq olmadı', e.message); diagnostics(); return;
  }
  window.addEventListener('devicemotion', onMotion);
  wakeLock = await navigator.wakeLock?.request('screen').catch(() => null);
  $('#setup').hidden = true; $('#live').hidden = false; $('#test').hidden = false;
  setStatus('', 'Sakit', 'Sensor kalibrasiya olunur (3 san), telefonu tərpətməyin');
  requestAnimationFrame(draw);
  send();
  setInterval(() => send(), 2000);
  setInterval(() => {rate = events; events = 0; if (!rate && window.isSecureContext === false) setStatus('confirmed', 'Sensor məlumatı gəlmir', 'Səhifəni HTTPS ünvanı ilə açın (BASLAT-SENSOR.cmd və ya start.py --https)');}, 1000);
});

$('#test').addEventListener('click', () => {
  setStatus('shake', 'SINAQ SİQNALI', 'Simulyasiya edilmiş titrəmə göndərildi');
  send({triggered: true, test: true, peak: 6});
});
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && wakeLock?.released) wakeLock = await navigator.wakeLock.request('screen').catch(() => null);
});
diagnostics();
