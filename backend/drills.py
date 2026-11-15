"""Room-scoped earthquake drills. No Google integration and no real SOS creation.

Transient, single-process presentation transport. A restart clears membership and
events, so an old alarm cannot be replayed as a new incident.
"""
import asyncio
import time
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Device(Strict):
    device_id: UUID
    room: str = Field(pattern=r'^[A-Z0-9-]{3,16}$')
    label: str = Field(min_length=1, max_length=40)
    audio_ready: bool = False


class Earthquake(Strict):
    event_key: UUID
    room: str = Field(pattern=r'^[A-Z0-9-]{3,16}$')
    location: str = Field(min_length=1, max_length=80)
    magnitude: float = Field(ge=2, le=9)
    duration: int = Field(default=30, ge=10, le=60)


class Receipt(Strict):
    device_id: UUID
    status: Literal['received', 'audio_started', 'muted', 'acknowledged']


class DrillHub:
    def __init__(self, clock):
        self.clock = clock
        self.devices = {}
        self.events = {}

    def prune(self):
        now = self.clock()
        self.devices = {k: v for k, v in self.devices.items() if now-v['seen'] < 120}
        # Retain retry keys and receipts for ten minutes, with hard capacity caps.
        self.events = {k: v for k, v in self.events.items() if now-v['created_at'] < 600}

    def own(self, device_id, owner):
        member = self.devices.get(str(device_id))
        if not member or member['owner'] != owner:
            raise HTTPException(404, 'device_not_found')
        return member

    def active(self, room):
        return next((e for e in reversed(list(self.events.values()))
                     if e['room'] == room and not e['cancelled']
                     and e['expires_at'] > self.clock()), None)

    @staticmethod
    def public(event):
        return {k: v for k, v in event.items() if k not in ('owner', 'receipts', 'event_key')}

    def packet(self, device_id, owner):
        self.prune()
        member = self.own(device_id, owner)
        member['seen'] = self.clock()
        event = self.active(member['room'])
        connected = [m for m in self.devices.values()
                     if m['room'] == member['room'] and self.clock()-m['seen'] < 15]
        return {'server_time': self.clock(), 'room': member['room'],
                'connected': len(connected),
                'audio_ready': sum(m['audio_ready'] for m in connected),
                'event': self.public(event) if event else None}


def install_drills(app, store, require, user_from, origin_ok, throttle, demo):
    hub = DrillHub(store.clock)
    app.state.drills = hub

    def authorize(request, permission=None):
        if not demo:
            raise HTTPException(404, 'not_found')
        return require(request, permission)

    @app.post('/api/drills/devices')
    def join(body: Device, request: Request):
        user = authorize(request)
        throttle('drill-join:'+user['id'], 30)
        key = str(body.device_id)
        with store.lock:
            hub.prune()
            if key in hub.devices:
                hub.own(key, user['id'])
            elif len(hub.devices) >= 500:
                raise HTTPException(503, 'drill_capacity')
            hub.devices[key] = {'owner': user['id'], 'room': body.room,
                                'label': body.label, 'audio_ready': body.audio_ready,
                                'seen': hub.clock()}
            return hub.packet(key, user['id'])

    @app.delete('/api/drills/devices/{device_id}')
    def leave(device_id: UUID, request: Request):
        user = authorize(request)
        with store.lock:
            hub.own(device_id, user['id'])
            del hub.devices[str(device_id)]
        return {'ok': True}

    @app.get('/api/drills/poll')
    def poll(device_id: UUID, request: Request):
        user = authorize(request)
        with store.lock:
            return hub.packet(device_id, user['id'])

    @app.post('/api/drills/earthquake')
    def publish(body: Earthquake, request: Request):
        user = authorize(request, 'demo:write')
        with store.lock:
            hub.prune()
            prior = next((e for e in hub.events.values()
                          if e['owner'] == user['id'] and e['event_key'] == str(body.event_key)), None)
            if prior:
                if any(prior[k] != getattr(body, k) for k in ('room', 'location', 'magnitude', 'duration')):
                    raise HTTPException(409, 'event_key_conflict')
                return hub.public(prior)
            throttle('drill-publish:'+user['id'], 6)
            if hub.active(body.room):
                raise HTTPException(409, 'drill_already_active')
            if len(hub.events) >= 200:
                raise HTTPException(503, 'drill_capacity')
            event = dict(body.model_dump(mode='json'), id=str(uuid4()),
                         owner=user['id'], created_at=hub.clock(),
                         expires_at=hub.clock()+body.duration, cancelled=False,
                         source='DigiMinds simulation', simulated=True, receipts={})
            hub.events[event['id']] = event
            return hub.public(event)

    @app.post('/api/drills/earthquake/{event_id}/cancel')
    def cancel(event_id: UUID, request: Request):
        authorize(request, 'demo:write')
        with store.lock:
            event = hub.events.get(str(event_id))
            if not event:
                raise HTTPException(404, 'drill_not_found')
            event['cancelled'] = True
        return {'ok': True}

    @app.post('/api/drills/earthquake/{event_id}/receipts')
    def receipt(event_id: UUID, body: Receipt, request: Request):
        user = authorize(request)
        with store.lock:
            member = hub.own(body.device_id, user['id'])
            event = hub.events.get(str(event_id))
            if not event or event['room'] != member['room']:
                raise HTTPException(404, 'drill_not_found')
            if event['cancelled'] or event['expires_at'] <= hub.clock():
                raise HTTPException(409, 'drill_ended')
            event['receipts'].setdefault(str(body.device_id), {}).setdefault(body.status, hub.clock())
        return {'ok': True}

    @app.get('/api/drills/rooms/{room}')
    def status(room: str, request: Request):
        authorize(request, 'demo:write')
        with store.lock:
            hub.prune()
            events = [e for e in hub.events.values() if e['room'] == room]
            latest = events[-1] if events else None
            members = [{'label': m['label'], 'device_id': key,
                        'online': hub.clock()-m['seen'] < 15,
                        'audio_ready': m['audio_ready'],
                        'receipt': latest['receipts'].get(key, {}) if latest else {}}
                       for key, m in hub.devices.items() if m['room'] == room]
            return {'devices': members, 'event': hub.public(latest) if latest else None,
                    'server_time': hub.clock()}

    @app.websocket('/ws/drills')
    async def socket(ws: WebSocket):
        user = user_from(ws.headers, ws.cookies)
        if not demo or not user or not origin_ok(ws.headers, ws.url):
            await ws.close(code=1008)
            return
        device_id = ws.query_params.get('device_id', '')
        try:
            throttle('drill-ws:'+user['id'], 20)
            with store.lock:
                hub.own(device_id, user['id'])
        except HTTPException:
            await ws.close(code=1008)
            return
        await ws.accept()
        last = None
        sent = 0
        try:
            while True:
                user = user_from(ws.headers, ws.cookies)
                if not user:
                    await ws.close(code=1008)
                    break
                with store.lock:
                    packet = hub.packet(device_id, user['id'])
                signature = (packet['room'], packet['connected'], packet['audio_ready'],
                             packet['event']['id'] if packet['event'] else None)
                if signature != last or time.monotonic()-sent >= 5:
                    await asyncio.wait_for(ws.send_json(packet), timeout=3)
                    last, sent = signature, time.monotonic()
                await asyncio.sleep(.4)
        except HTTPException:
            await ws.close(code=1008)
        except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError):
            pass
