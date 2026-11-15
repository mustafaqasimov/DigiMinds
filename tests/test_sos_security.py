import asyncio
import time
import uuid

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.security import Limiter, token_hash
from backend.sos_guard import SOSGuard
from backend.store import Store
from test_engine import body, guest, login, wave


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path/'security.db'),demo=True)


@pytest.fixture
def client(app):
    with TestClient(app) as c:yield c


def test_jwt_claims_signature_algorithm_and_session_are_all_required(client,app):
    header=login(client)
    token=header['Authorization'][7:]
    claims=jwt.decode(token,app.state.tokens.secret,algorithms=['HS256'],audience='crisis-api',issuer='digiminds')
    assert claims['role']=='dispatcher' and claims['exp']>claims['iat']
    variants=[jwt.encode({**claims,'role':'admin'},'attacker-key-that-is-at-least-32-bytes',algorithm='HS256'),
              jwt.encode(claims,'',algorithm='none'),
              jwt.encode(claims,app.state.tokens.secret,algorithm='HS384'),
              jwt.encode({**claims,'exp':int(time.time())-1},app.state.tokens.secret,algorithm='HS256'),
              jwt.encode({**claims,'aud':'different-api'},app.state.tokens.secret,algorithm='HS256'),
              jwt.encode({k:v for k,v in claims.items() if k!='exp'},app.state.tokens.secret,algorithm='HS256')]
    for invalid in variants:
        # Even a matching DB session cannot make an invalid JWT valid.
        with app.state.store.lock,app.state.store.db:
            app.state.store.db.execute('INSERT INTO sessions VALUES(?,?,?)',(token_hash(invalid),claims['sub'],time.time()+100))
        r=client.get('/api/auth/me',headers={'Authorization':'Bearer '+invalid})
        assert r.status_code==401 and r.headers['WWW-Authenticate']=='Bearer'
    unregistered,_=app.state.tokens.issue({'id':claims['sub'],'role':'dispatcher'})
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+unregistered}).status_code==401
    assert client.get('/api/auth/me',headers={'Authorization':'Basic invalid'}).status_code==401
    assert client.get('/api/auth/me',headers=header).status_code==200


@pytest.mark.parametrize('role',['citizen','priority_citizen','observer','responder'])
def test_dispatch_and_shelter_actions_deny_non_operators(client,app,role):
    wave(client)
    alert=app.state.store.objects('alert')[0]['id']
    header=guest(client) if role=='citizen' else login(client,role)
    for action in ('dispatch','open_shelter','respond'):
        assert client.post(f'/api/alerts/{alert}/{action}',headers=header).status_code==403
    assert not app.state.store.db.execute('SELECT * FROM actions').fetchall()
    assert all(t['status']=='available' for t in app.state.store.objects('team'))


def test_demotion_is_immediate_even_with_valid_old_jwt(client,app):
    wave(client);header=login(client)
    user_id=client.get('/api/auth/me',headers=header).json()['id']
    alert=app.state.store.objects('alert')[0]['id']
    with app.state.store.lock,app.state.store.db:
        app.state.store.db.execute("UPDATE users SET role='observer' WHERE id=?",(user_id,))
    assert client.post(f'/api/alerts/{alert}/dispatch',headers=header).status_code==403


def test_new_key_quota_is_shared_by_sessions_but_existing_retry_survives(client,app):
    first=guest(client);user=client.get('/api/auth/me',headers=first).json()
    second_token,expires=app.state.tokens.issue(user)
    with app.state.store.lock,app.state.store.db:
        app.state.store.db.execute('INSERT INTO sessions VALUES(?,?,?)',(token_hash(second_token),user['id'],expires))
    second={'Authorization':'Bearer '+second_token}
    payloads=[body() for _ in range(8)]
    for i,payload in enumerate(payloads):
        assert client.post('/api/sos',headers=first if i%2 else second,json=payload).status_code in (200,201)
    r=client.post('/api/sos',headers=second,json=body())
    assert r.status_code==429 and int(r.headers['Retry-After'])>0
    replay=client.post('/api/sos',headers=second,json=payloads[-1])
    assert replay.status_code==200 and replay.headers['X-SOS-Duplicate']=='true'
    assert app.state.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]==1


def test_duplicate_delivery_alias_persists_and_cannot_change_payload(tmp_path):
    path=str(tmp_path/'deliveries.db');now=[1000.]
    store=Store(path,lambda:now[0])
    first,_=store.report('person','original-key','fire',40.3725,49.8385)
    alias,_=store.report('person','another-key','fire',40.3726,49.8385)
    assert alias['id']==first['id']
    store.db.close();now[0]+=3600;store=Store(path,lambda:now[0])
    replay,created=store.report('person','another-key','fire',40.3726,49.8385)
    assert not created and replay['id']==first['id']
    with pytest.raises(ValueError,match='idempotency_conflict'):
        store.report('person','another-key','medical',40.3726,49.8385)
    assert store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]==1


def test_limiter_is_bounded_without_resetting_live_keys():
    now=[0.];limiter=Limiter(max_keys=2,clock=lambda:now[0])
    assert limiter.allow('a',1,60)[0] and limiter.allow('b',1,60)[0]
    for i in range(1000):assert not limiter.allow('new-'+str(i),1,60)[0]
    assert len(limiter.events)==len(limiter.expiry)==2
    assert not limiter.allow('a',1,60)[0]
    now[0]=60
    assert limiter.allow('new',1,60)[0] and len(limiter.events)==1


@pytest.mark.parametrize('path',['/api/sos','/api/seismic/warning/checkin'])
def test_rejected_flood_does_not_read_request_body_or_trust_x_forwarded_for(app,path):
    async def run():
        called=[]
        async def downstream(*args):raise AssertionError('Invalid JWT reached application')
        async def receive():raise AssertionError('Rejected request body was read')
        async def send(message):
            if message['type']=='http.response.start':called.append(message['status'])
        guard=SOSGuard(downstream,Limiter(),app.state.tokens)
        scope={'type':'http','method':'POST','path':path,'client':('192.0.2.1',1),'headers':[]}
        for i in range(1201):
            scope['headers']=[(b'x-forwarded-for',str(i).encode())]
            await guard(scope,receive,send)
        assert called[:1200]==[401]*1200 and called[-1]==429
    asyncio.run(run())


def test_seismic_help_cannot_bypass_sos_quota_and_changed_retry_is_conflict(client,app):
    operator=login(client)
    client.post('/api/demo/seismic',headers=operator,json={'devices':1})
    person=guest(client)
    reading={'label':'test','lat':40.3725,'lng':49.8385,'level':3,'peak':8,'ratio':40,'triggered':True}
    warning=client.post('/api/sensors/reading',headers=person,json=reading).json()['seismic'][0]['id']
    for _ in range(8):
        assert client.post('/api/sos',headers=person,json=body()).status_code in (200,201)
    url=f'/api/seismic/{warning}/checkin'
    payload={'status':'need_help','lat':40.3725,'lng':49.8385}
    assert client.post(url,headers=person,json=payload).status_code==429
    other=guest(client)
    first=client.post(url,headers=other,json=payload)
    assert first.status_code==200 and first.json()['sos']
    assert client.post(url,headers=other,json=payload).json()['sos']==first.json()['sos']
    assert client.post(url,headers=other,json={**payload,'lat':40.38}).status_code==409


def test_evaluation_cache_expires_seismic_independently_of_sos(tmp_path):
    now=[1000.];store=Store(str(tmp_path/'seismic-expiry.db'),lambda:now[0])
    with store.lock,store.db:
        for i in range(3):
            store.db.execute('INSERT INTO seismic VALUES(?,?,?,?,?,?,?,?,?)',
                             (f'r{i}',f'd{i}','test',40.3725,49.8385,8,40,0,now[0]))
    now[0]=1200.
    store.report('later-user','later-key','fire',40.3725,49.8385)
    assert store.snapshot()['seismic']
    now[0]=1300.
    assert store.snapshot()['seismic']  # Inclusive hold boundary.
    now[0]=1300.0001
    assert not store.snapshot()['seismic']


def test_600_concurrent_sos_keep_dispatch_and_legitimate_sos_available(client,app):
    wave(client);operator=login(client);attacker=guest(client);genuine=guest(client)
    alert=app.state.store.objects('alert')[0]['id'];payload=body()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            requests=[c.post('/api/sos',headers=attacker,json=payload) for _ in range(600)]
            requests += [c.post('/api/sos',headers=genuine,json=body(type='medical')),
                         c.get('/api/state',headers=operator),
                         c.post(f'/api/alerts/{alert}/dispatch',headers=operator)]
            responses=await asyncio.gather(*requests)
            attack=responses[:600]
            assert all(r.status_code in (200,201,429) for r in attack)
            assert sum(r.status_code==201 for r in attack)==1
            assert sum(r.status_code==429 for r in attack)>=540
            assert all(int(r.headers['Retry-After'])>=1 for r in attack if r.status_code==429)
            assert [r.status_code for r in responses[600:]]==[201,200,200]
            assert len(responses[601].json()['reports'])<=6
    asyncio.run(run())
    assert app.state.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]==6
    assert app.state.store.db.execute('SELECT COUNT(*) FROM actions').fetchone()[0]==1


def test_jwt_secret_required_for_production(tmp_path,monkeypatch):
    monkeypatch.delenv('JWT_SECRET',raising=False)
    with pytest.raises(RuntimeError,match='JWT_SECRET'):
        create_app(str(tmp_path/'production.db'),demo=False)


def test_capacity_is_released_after_downstream_exception(app):
    token,_=app.state.tokens.issue({'id':'fixture','role':'citizen'})
    async def run():
        async def downstream(*args):raise RuntimeError('fixture failure')
        async def receive():return {'type':'http.request','body':b'','more_body':False}
        async def send(message):raise AssertionError('Unexpected admission rejection')
        guard=SOSGuard(downstream,Limiter(),app.state.tokens,max_active=1)
        scope={'type':'http','method':'POST','path':'/api/sos','client':('192.0.2.1',1),
               'headers':[(b'authorization',('Bearer '+token).encode())]}
        for _ in range(2):
            with pytest.raises(RuntimeError,match='fixture failure'):await guard(scope,receive,send)
            assert guard.active==0 and not guard.by_user
    asyncio.run(run())


def test_cached_claims_do_not_extend_jwt_expiration(app,monkeypatch):
    from backend import security
    token,_=app.state.tokens.issue({'id':'fixture','role':'citizen'})
    assert app.state.tokens.verify(token)
    digest=token_hash(token)
    # A cached entry already at expiry must be reverified, not returned.
    app.state.tokens.verified[digest]=(time.time()-1,{'sub':'stale'})
    monkeypatch.setattr(security.jwt,'decode',lambda *a,**k:(_ for _ in ()).throw(jwt.ExpiredSignatureError()))
    assert app.state.tokens.verify(token) is None
