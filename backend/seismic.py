"""Vibration-based earthquake signals from phone accelerometers, and citizen check-ins.

Each phone on /sensor runs a recursive STA/LTA trigger (frontend/seismic.js) and
reports onsets. One phone alone is never an earthquake (a dropped phone, a
footstep): the server confirms a shake only when enough distinct devices trigger
close in time and space. A confirmed shake is a public warning, rings the
existing drill alarm on connected devices (demo mode) and asks citizens to report
their status. Not an official early-warning service and not connected to Google.
"""
import math
import time
import uuid
import anyio
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .geo import distance

# Check-in statuses that need responders become ordinary SOS reports.
CHECKIN_SOS = {'need_help': 'medical', 'trapped': 'collapse'}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class SensorReading(Strict):
    label: str = Field(min_length=1, max_length=30)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    level: float = Field(ge=0, le=200)
    peak: float = Field(default=0, ge=0, le=200)
    ratio: float = Field(default=0, ge=0, le=10000)
    triggered: bool = False
    test: bool = False


class SeismicConfig(Strict):
    devices: int = Field(ge=1, le=10)


class CheckIn(Strict):
    status: Literal['safe', 'need_help', 'trapped']
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


def events(store, now, cfg):
    """Alert triggers for confirmed shakes, in Store.evaluate's (key, kind, target, evidence) format."""
    window = cfg.get('seismic_window_seconds', 10)
    needed = cfg.get('seismic_devices', 3)
    radius = cfg.get('seismic_radius_m', 1000)
    hold = cfg.get('seismic_hold_seconds', 300)
    rows = [dict(r) for r in store.db.execute(
        'SELECT * FROM seismic WHERE created>=? AND created<=? ORDER BY created,id LIMIT 500',
        (now - hold - window, now))]
    used, found = set(), []
    for first in rows:
        if first['id'] in used or now - first['created'] > hold:
            continue
        members = [r for r in rows if r['id'] not in used
                   and first['created'] <= r['created'] <= first['created'] + window
                   and distance((first['lat'], first['lng']), (r['lat'], r['lng'])) <= radius]
        devices = {}
        for r in members:
            devices.setdefault(r['device'], r)
        if len(devices) < needed:
            continue
        used.update(r['id'] for r in members)
        chosen = list(devices.values())
        found.append(('seismic:' + first['id'], 'seismic', first['id'], {
            'devices': len(chosen), 'needed': needed, 'labels': sorted(r['label'] for r in chosen),
            'peak': round(max(r['peak'] for r in chosen), 2),
            'spread_seconds': round(max(r['created'] for r in chosen) - first['created'], 1),
            'lat': sum(r['lat'] for r in chosen) / len(chosen), 'lng': sum(r['lng'] for r in chosen) / len(chosen),
            'test': any(r['test'] for r in chosen)}))
    return found


def magnitude_hint(peak):
    """Rough demo scale only: phone peaks of ~2-16 m/s^2 map onto M5.0-7.5."""
    return round(min(7.5, max(5.0, 5 + math.log2(max(peak, .1) / 2))), 1)


def snapshot(store, user, now):
    """Public warning, the viewer's own check-in, and dispatcher summaries."""
    active = [a for a in store.objects('alert') if a['kind'] == 'seismic' and a.get('condition_active')]
    result = {'seismic': [{'id': a['id'], 'created': a['created'],
                           **{k: a['evidence'][k] for k in ('devices', 'needed', 'peak', 'test')}} for a in active]}
    if user:
        mine = {r['alert_id']: r['status'] for r in store.db.execute(
            'SELECT alert_id,status FROM checkins WHERE user_id=?', (user['id'],))}
        for item in result['seismic']:
            item['my_status'] = mine.get(item['id'])
    if user and 'dashboard:read' in user.get('permissions', []):
        result['sensors'] = [d for d in store.objects('device') if now - d['last_seen'] <= 30]
        for item in result['seismic']:
            rows = [dict(r) for r in store.db.execute(
                'SELECT status,lat,lng,created FROM checkins WHERE alert_id=?', (item['id'],))]
            item['checkins'] = {s: sum(r['status'] == s for r in rows) for s in ('safe', 'need_help', 'trapped')}
            item['help_points'] = [r for r in rows if r['status'] != 'safe'][:200]
    return result


def install_seismic(app, store, require, throttle, demo, sos_workers):
    def drill_alarm(alert):
        """Demo: ring the existing drill alarm in every room that has connected devices."""
        hub = getattr(app.state, 'drills', None)
        if not demo or not hub:
            return []
        now = hub.clock()
        rooms = {m['room'] for m in hub.devices.values() if now - m['seen'] < 15}
        e = alert['evidence']
        rung = []
        for room in sorted(rooms):
            if hub.active(room):
                continue
            event_id = str(uuid.uuid4())
            hub.events[event_id] = {
                'id': event_id, 'event_key': event_id, 'room': room, 'owner': 'sensor',
                'location': f"{e['devices']} sensor · {e['peak']} m/s²", 'magnitude': magnitude_hint(e['peak']),
                'duration': 30, 'message': 'Telefon sensorları eyni anda titrəmə qeydə aldı. Çök, örtün, tutun.',
                'created_at': now, 'expires_at': now + 30, 'cancelled': False,
                'source': 'DigiMinds sensors', 'simulated': True, 'receipts': {}}
            rung.append(room)
        return rung

    @app.post('/api/sensors/reading')
    def sensor_reading(body: SensorReading, request: Request):
        """Phone accelerometer heartbeat; triggered=True reports a local STA/LTA onset."""
        u = require(request)
        throttle('sensor:' + u['id'], 90)
        with store.lock, store.db:
            now = time.time()
            cfg = store.config()
            device = store.get('device', u['id']) or {'id': u['id'], 'triggered_at': 0}
            fresh = now - device.get('last_seen', 0) > 30
            device.update(label=body.label, lat=body.lat, lng=body.lng, level=round(body.level, 3), last_seen=now)
            if body.triggered and now - device['triggered_at'] >= 2:
                throttle('sensor-trigger:' + u['id'], 20)
                device['triggered_at'] = now
                store.db.execute('INSERT INTO seismic VALUES(?,?,?,?,?,?,?,?,?)',
                                 (uuid.uuid4().hex, u['id'], body.label, body.lat, body.lng,
                                  body.peak, body.ratio, int(body.test), now))
                before = {a['key'] for a in store.objects('alert') if a['kind'] == 'seismic'}
                store.put('device', device)
                store.audit(u['id'], 'sensor.trigger', body.label)
                store.evaluate()
                for a in store.objects('alert'):
                    if a['kind'] == 'seismic' and a['key'] not in before:
                        rooms = drill_alarm(a)
                        store.audit('sensor', 'seismic.confirmed', f"{a['id']} rooms={len(rooms)}")
            else:
                store.put('device', device)
                if fresh:
                    store.revision += 1
            online = sum(now - d['last_seen'] <= 30 for d in store.objects('device'))
            active = snapshot(store, None, now)['seismic']
        return {'ok': True, 'devices_online': online, 'needed': cfg.get('seismic_devices', 3), 'seismic': active}

    def process_checkin(alert_id, body, request):
        """Citizen status after a warning. Help/trapped become SOS reports for dispatch."""
        u = require(request, 'sos:own')
        throttle('checkin:' + u['id'], 20)
        with store.lock, store.db:
            store.evaluate()
            alert = store.get('alert', alert_id)
            if not alert or alert['kind'] != 'seismic':
                raise HTTPException(404, 'not_found')
            if not alert.get('condition_active'):
                raise HTTPException(409, 'warning_ended')
            event_key = f'checkin-{alert_id}-{body.status}'
            if body.status != 'safe' and not store.report_by_key(u['id'], event_key):
                throttle('sos:' + u['id'], 8)
            now = store.clock()
            store.db.execute('INSERT OR REPLACE INTO checkins VALUES(?,?,?,?,?,?)',
                             (alert_id, u['id'], body.status, body.lat, body.lng, now))
            report = None
            if body.status == 'safe':
                store.safe(u['id'])
            else:
                report, _ = store.report(u['id'], event_key,
                                         CHECKIN_SOS[body.status], body.lat, body.lng)
            store.audit(u['id'], 'seismic.checkin', body.status)
        return {'status': body.status, 'sos': report['id'] if report else None}

    @app.post('/api/seismic/{alert_id}/checkin')
    async def checkin(alert_id: str, body: CheckIn, request: Request):
        try:
            return await anyio.to_thread.run_sync(process_checkin,alert_id,body,request,limiter=sos_workers)
        except ValueError as exc:
            raise HTTPException(409,str(exc))

    @app.post('/api/demo/seismic')
    def seismic_config(body: SeismicConfig, request: Request):
        u = require(request, 'demo:write')
        if not demo:
            raise HTTPException(404, 'not_found')
        with store.lock, store.db:
            c = store.config()
            c['seismic_devices'] = body.devices
            store.put('config', c)
            store.audit(u['id'], 'demo.seismic', str(body.devices))
        return {'ok': True, 'devices': body.devices}

    @app.post('/api/demo/seismic/reset')
    def seismic_reset(request: Request):
        u = require(request, 'demo:write')
        if not demo:
            raise HTTPException(404, 'not_found')
        with store.lock, store.db:
            store.db.execute('DELETE FROM seismic')
            store.db.execute('DELETE FROM checkins')
            for a in store.objects('alert'):
                if a['kind'] == 'seismic':
                    store.db.execute("DELETE FROM objects WHERE kind='alert' AND id=?", (a['id'],))
            store.audit(u['id'], 'demo.seismic_reset', 'all')
        return {'ok': True}
