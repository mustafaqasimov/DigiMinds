import asyncio
import contextlib
import json
import math
import os
import secrets
import time
from pathlib import Path
from typing import Literal
import httpx
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from .store import Store, uid
from .security import Limiter, password_hash, check_password, token_hash, PERMISSIONS
from .geo import blocked_polygons, crosses_closure, distance
from .circuit import CircuitBreaker
from .drills import install_drills
from .profiles import ProfileUpdate, profile_record, shared_profiles
from .vision_jobs import VisionJobs, install_vision, MAX_UPLOAD

ROOT=Path(__file__).resolve().parent.parent


class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


class Login(StrictModel):
    username:str=Field(min_length=1,max_length=80)
    password:str=Field(min_length=1,max_length=200)
    cookie_session:bool=True


class SOS(StrictModel):
    event_key:str=Field(min_length=8,max_length=80)
    type:Literal['fire','collapse','flood','medical']
    lat:float=Field(ge=-90,le=90)
    lng:float=Field(ge=-180,le=180)
    incident_id:str|None=Field(default=None,max_length=40)
    client_time:float|None=None


class Occupancy(StrictModel):
    occupancy:int=Field(ge=0,le=1000000)
    source:Literal['manual','yolo','simulation']='manual'
    observed_at:float|None=None
    coverage:Literal['full','partial']='full'
    density_people_m2:float|None=Field(default=None,ge=0,le=1000)


class RoleBody(StrictModel):
    name:str=Field(pattern=r'^[a-z][a-z0-9_-]{2,30}$')
    permissions:list[str]=Field(max_length=20)


class TeamStatus(StrictModel):
    status:Literal['en_route','on_scene','available']


class Switch(StrictModel):
    enabled:bool


class ProviderScenario(StrictModel):
    mode:Literal['off','healthy','http_503','slow']


class Assignment(StrictModel):
    role:str=Field(max_length=40)
    team_id:str|None=Field(default=None,max_length=40)


def create_app(db_path=None,demo=None):
    demo=(os.getenv('DEMO_MODE','1')=='1') if demo is None else demo
    store=Store(db_path or os.getenv('DATABASE_PATH',str(ROOT/'data/crisis.db')))
    limiter=Limiter()
    vision_jobs=VisionJobs(ROOT,Path(db_path or os.getenv('DATABASE_PATH',str(ROOT/'data/crisis.db'))).resolve().parent/'vision-jobs')
    @contextlib.asynccontextmanager
    async def lifespan(application):
        try:
            yield
        finally:
            vision_jobs.close()
    application=FastAPI(title='DigiMinds · Urban Crisis Engine',version='0.1.0',lifespan=lifespan)
    application.state.vision_jobs=vision_jobs
    application.state.store=store;application.state.limiter=limiter
    application.state.routing_circuit=CircuitBreaker()
    application.state.provider_timeout=4.5
    application.state.routing_transport=None
    with store.lock,store.db:
        if demo:
            for role in ('dispatcher','admin','responder','observer'):
                if not store.db.execute('SELECT id FROM users WHERE username=?',('demo-'+role,)).fetchone():
                    store.db.execute('INSERT INTO users VALUES(?,?,?,?,?)',(uid(),'demo-'+role,role,password_hash('demo'),'t1' if role=='responder' else None))
        else:
            # A database previously used in demo must not retain demo credentials.
            store.db.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'demo-%')")
            store.db.execute("DELETE FROM users WHERE username LIKE 'demo-%'")
            if not store.db.execute("SELECT id FROM users WHERE username='admin'").fetchone():
                password=os.getenv('ADMIN_PASSWORD','')
                if len(password)<16:raise RuntimeError('ADMIN_PASSWORD must contain at least 16 characters in production mode')
                store.db.execute('INSERT INTO users VALUES(?,?,?,?,NULL)',(uid(),'admin','admin',password_hash(password)))

    def origin_ok(headers,url):
        origin=headers.get('origin')
        if not origin:return True
        allowed=set(os.getenv('ALLOWED_ORIGINS','').split(','))
        same=f'{"https" if url.scheme in ("https","wss") else "http"}://{headers.get("host",url.netloc)}'
        return origin==same or origin in allowed

    @application.middleware('http')
    async def guards(request,call_next):
        if request.method in ('POST','PUT','PATCH','DELETE'):
            if not origin_ok(request.headers,request.url):
                return Response('Origin rejected',403)
            if not request.headers.get('authorization') and request.headers.get('x-requested-with')!='DigiMinds':
                return Response('CSRF header required',403)
            try:
                declared=int(request.headers.get('content-length','0') or 0)
            except ValueError:
                return Response('Invalid content length',400)
            if declared<0:return Response('Invalid content length',400)
            video_upload=request.method=='POST' and request.url.path=='/api/vision/jobs'
            body_limit=MAX_UPLOAD if video_upload else 65536
            if declared>body_limit:return Response('Body too large',413)
            # Also enforce the bound for chunked requests without Content-Length.
            # Video route authenticates first and streams to disk with its own byte cap.
            if not video_upload:
                chunks=[];received=0
                async for chunk in request.stream():
                    received+=len(chunk)
                    if received>65536:return Response('Body too large',413)
                    chunks.append(chunk)
                request._body=b''.join(chunks)
        result=await call_next(request)
        result.headers['X-Content-Type-Options']='nosniff'
        result.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        result.headers['X-Frame-Options']='DENY'
        result.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; media-src 'self' blob:; connect-src 'self' ws: wss:; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        if request.url.path.startswith('/api'):result.headers['Cache-Control']='no-store'
        elif request.url.path=='/' or request.url.path.endswith(('.html','.js','.css')):result.headers['Cache-Control']='no-cache'
        return result

    def throttle(key,limit,window=60):
        ok,retry=limiter.allow(key,limit,window)
        if not ok:raise HTTPException(429,'rate_limited',headers={'Retry-After':str(retry)})

    def user_from(headers,cookies):
        bearer=headers.get('authorization','')
        token=bearer[7:] if bearer.startswith('Bearer ') else cookies.get('dm_session','')
        with store.lock:
            r=store.db.execute('SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(token_hash(token),time.time())).fetchone()
            if not r:return None
            u=dict(r);u.pop('password',None)
            role=store.get('role',u['role'])
            u['permissions']=role['permissions'] if role else []
            return u

    def require(request,permission=None):
        u=user_from(request.headers,request.cookies)
        if not u:raise HTTPException(401,'authentication_required')
        if permission and permission not in u['permissions']:raise HTTPException(403,'permission_denied')
        throttle('api:'+u['id'],300)
        return u

    def issue(user,response,cookie_session=True):
        token=secrets.token_urlsafe(32)
        with store.lock,store.db:
            store.db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            store.db.execute('INSERT INTO sessions VALUES(?,?,?)',(token_hash(token),user['id'],time.time()+8*3600))
        if cookie_session:response.set_cookie('dm_session',token,httponly=True,samesite='strict',secure=os.getenv('SECURE_COOKIES')=='1',max_age=28800)
        if cookie_session and user['role']=='citizen':
            response.set_cookie('dm_citizen',token,httponly=True,samesite='strict',secure=os.getenv('SECURE_COOKIES')=='1',max_age=28800)
        # Bearer token lets CLI/load tests use the same authentication scheme.
        return {'token':token,'user':{k:v for k,v in user.items() if k!='password'},'demo':demo}

    @application.get('/api/health')
    def health():return {'ok':True,'demo':demo,'external_routing_configured':bool(os.getenv('ORS_API_KEY')),'dataset':'synthetic-training-baku-v1'}

    @application.post('/api/auth/guest')
    def guest(request:Request,response:Response):
        throttle('guest:'+request.client.host,40)
        previous=user_from({}, {'dm_session':request.cookies.get('dm_citizen','')})
        if previous and previous['role']=='citizen':return issue(previous,response)
        with store.lock,store.db:
            u={'id':uid(),'username':'guest-'+uid()[:8],'role':'citizen','team_id':None}
            store.db.execute('INSERT INTO users VALUES(?,?,?,NULL,NULL)',(u['id'],u['username'],u['role']))
        return issue(u,response)

    @application.post('/api/auth/login')
    def login(body:Login,request:Request,response:Response):
        throttle('login-ip:'+request.client.host,12)
        throttle('login-name:'+body.username,8)
        with store.lock:
            r=store.db.execute('SELECT * FROM users WHERE username=?',(body.username,)).fetchone()
        if not r or not r['password'] or not check_password(body.password,r['password']):raise HTTPException(401,'invalid_credentials')
        return issue(dict(r),response,body.cookie_session)

    @application.get('/api/auth/me')
    def me(request:Request):return require(request)

    @application.post('/api/auth/logout')
    def logout(request:Request,response:Response):
        u=require(request)
        bearer=request.headers.get('authorization','')
        token=bearer[7:] if bearer.startswith('Bearer ') else request.cookies.get('dm_session','')
        with store.lock,store.db:store.db.execute('DELETE FROM sessions WHERE token=?',(token_hash(token),))
        response.delete_cookie('dm_session');return {'ok':True}

    @application.get('/api/state')
    def state(request:Request):return store.snapshot(require(request))

    def citizen(request):
        u = require(request)
        if u['role'] != 'citizen':raise HTTPException(403, 'citizen_profile_only')
        return u

    @application.get('/api/me/profile')
    def get_profile(request:Request):
        u = citizen(request)
        with store.lock:return profile_record(store, u['id'])

    @application.put('/api/me/profile')
    def update_profile(body:ProfileUpdate, request:Request):
        u = citizen(request)
        with store.lock, store.db:
            current = profile_record(store, u['id'])
            if body.version != current['version']:raise HTTPException(409, 'profile_changed')
            profile = body.profile.model_dump()
            store.put('profile', {'id': u['id'], 'profile': profile, 'version': current['version']+1, 'updated_at': store.clock()})
            store.audit(u['id'], 'profile.saved', u['id'])
            if profile['share_on_sos'] != current['profile']['share_on_sos']:
                store.audit(u['id'], 'profile.sharing_enabled' if profile['share_on_sos'] else 'profile.sharing_disabled', u['id'])
            return profile_record(store, u['id'])

    @application.delete('/api/me/profile')
    def delete_profile(request:Request, version:int):
        u = citizen(request)
        with store.lock, store.db:
            current = profile_record(store, u['id'])
            if version != current['version']:raise HTTPException(409, 'profile_changed')
            # Keep only a version tombstone, so a stale tab cannot recreate deleted data.
            store.put('profile', {'id': u['id'], 'profile': None, 'version': current['version']+1, 'updated_at': None})
            store.audit(u['id'], 'profile.deleted', u['id'])
            return profile_record(store, u['id'])

    @application.get('/api/incidents/{id}/assistance')
    def incident_assistance(id:str, request:Request):
        u = require(request)
        with store.lock, store.db:
            assigned = any(t['id']==u.get('team_id') and t.get('incident_id')==id and t['status']!='available' for t in store.objects('team'))
            if 'incident:act' not in u['permissions'] and not ('assignment:read' in u['permissions'] and assigned):
                raise HTTPException(403, 'permission_denied')
            if not store.db.execute('SELECT id FROM incidents WHERE id=?', (id,)).fetchone():raise HTTPException(404, 'not_found')
            people = shared_profiles(store, id)
            # Audit metadata only: never copy personal fields into logs or WebSocket state.
            for person in people:
                owner = store.db.execute('SELECT user_id FROM reports WHERE id=?', (person['report_id'],)).fetchone()[0]
                store.audit(u['id'], 'profile.accessed', owner)
            return {'incident_id': id, 'people': people}

    @application.get('/api/map')
    def map_data():return store.snapshot()

    @application.post('/api/sos')
    def sos(body:SOS,request:Request,response:Response):
        u=require(request,'sos:create')
        # Idempotent retry is accepted without consuming a second SOS quota.
        with store.lock:
            old=store.db.execute('SELECT id FROM reports WHERE user_id=? AND event_key=?',(u['id'],body.event_key)).fetchone()
        if not old:throttle('sos:'+u['id'],8)
        try:
            r,created=store.report(u['id'],**body.model_dump())
        except ValueError as exc:raise HTTPException(409,str(exc))
        response.status_code=201 if created else 200
        return {'report':{k:v for k,v in r.items() if k!='user_id'},'created':created}

    @application.post('/api/me/safe')
    def safe(request:Request):
        u=require(request,'sos:own');store.safe(u['id']);return {'ok':True}

    @application.get('/api/routes')
    async def routes(request:Request,lat:float,lng:float,mode:Literal['auto','local']='auto'):
        started=time.monotonic()
        u=require(request);throttle('route:'+u['id'],30)
        if not (-90<=lat<=90 and -180<=lng<=180):raise HTTPException(422,'invalid_coordinates')
        with store.lock:
            try:choices=store.local_routes(lat,lng)
            except ValueError as exc:raise HTTPException(422,str(exc))
            cfg=store.config();polys=blocked_polygons(store.map['nodes'],store.objects('road'));revision=store.revision
        breaker=application.state.routing_circuit
        scenario=cfg.get('routing_demo','off') if demo else 'off'
        if cfg['provider_down'] and demo:scenario='http_503'
        configured=bool(os.getenv('ORS_API_KEY')) or scenario!='off'
        reason='local_selected' if mode=='local' else 'external_not_configured'
        attempted=False
        if choices and mode=='auto' and configured:
            permit,reason=breaker.acquire()
            if permit:
                attempted=True;success=None
                try:
                    destination=choices[0]['geometry'][-1]
                    body={'coordinates':[[lng,lat],destination]}
                    if polys:body['options']={'avoid_polygons':{'type':'MultiPolygon','coordinates':polys}}
                    transport=application.state.routing_transport
                    if scenario!='off':
                        async def simulate(req):
                            if scenario=='http_503':return httpx.Response(503,request=req,json={'error':'simulation'})
                            if scenario=='slow':await asyncio.sleep(6)
                            r=choices[0]
                            return httpx.Response(200,request=req,json={'features':[{'geometry':{'coordinates':r['geometry']},'properties':{'summary':{'distance':r['meters'],'duration':r['minutes']*60}}}]})
                        transport=httpx.MockTransport(simulate)
                    # A total wall-clock deadline includes connect/TLS, body and parsing.
                    # HTTPX read timeouts alone only bound gaps between body chunks.
                    async with asyncio.timeout(application.state.provider_timeout):
                        async with httpx.AsyncClient(timeout=httpx.Timeout(4.5,connect=2.,pool=.2),transport=transport) as client:
                            result=await client.post(os.getenv('ORS_URL','https://api.heigit.org/openrouteservice/v2/directions/foot-walking/geojson'),headers={'Authorization':os.getenv('ORS_API_KEY','demo')},json=body)
                            result.raise_for_status()
                            if len(result.content)>2_000_000:raise ValueError('provider_payload_too_large')
                            feature=result.json()['features'][0]
                            coords=feature['geometry']['coordinates'];summary=feature['properties']['summary']
                            if not isinstance(coords,list) or not 2<=len(coords)<=20000:raise ValueError('invalid_provider_route')
                            if any(not isinstance(p,list) or len(p)<2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in p[:2]) or not -180<=p[0]<=180 or not -90<=p[1]<=90 for p in coords):raise ValueError('invalid_coordinates')
                            meters,seconds=float(summary['distance']),float(summary['duration'])
                            if not all(math.isfinite(v) and v>=0 for v in (meters,seconds)):raise ValueError('invalid_summary')
                            if distance((lat,lng),(coords[0][1],coords[0][0]))>250 or distance((destination[1],destination[0]),(coords[-1][1],coords[-1][0]))>100 or crosses_closure(coords,polys):raise ValueError('invalid_provider_route')
                            choices[0].update(geometry=coords,meters=round(meters),minutes=round(seconds/60,1),source='simulated_provider' if scenario!='off' else 'external_ors')
                            success=True;reason=None
                except (TimeoutError,httpx.TimeoutException):success=False;reason='provider_timeout'
                except httpx.HTTPStatusError as exc:success=False;reason='provider_http_'+str(exc.response.status_code)
                except httpx.HTTPError:success=False;reason='provider_network_error'
                except (ValueError,KeyError,IndexError,TypeError,OverflowError):success=False;reason='invalid_provider_response'
                finally:breaker.finish(permit,success,reason)
        if cfg['provider_down'] and mode=='auto':reason='provider_unavailable'
        # Never return a cached external path through a newly closed road/full shelter.
        with store.lock:
            if store.revision!=revision:
                choices=store.local_routes(lat,lng);reason='state_changed_local_recalculation'
        if not choices:reason='no_eligible_route'
        service_mode='online' if reason is None else 'local' if reason in ('local_selected','external_not_configured','no_eligible_route') else 'fallback'
        routing={'mode':service_mode,'reason':reason,'circuit':breaker.snapshot(),
                 'deadline_ms':round(application.state.provider_timeout*1000),'elapsed_ms':round((time.monotonic()-started)*1000),
                 'external_attempted':attempted,'demo_provider':scenario!='off'}
        return {'routes':choices,'fallback_reason':reason,'routing':routing,
                'message':'Oflayn/ehtiyat marşrut rejimində işləyir' if service_mode=='fallback' else None,
                'calculated_at':time.time(),'dataset':'SIMULATION','no_route':not choices}

    @application.post('/api/demo/routing-provider')
    def routing_scenario(body:ProviderScenario,request:Request):
        u=require(request,'demo:write')
        if not demo:raise HTTPException(404,'not_found')
        with store.lock,store.db:
            cfg=store.config();cfg['routing_demo']=body.mode;cfg['provider_down']=False
            store.put('config',cfg);store.audit(u['id'],'demo.routing_provider',body.mode)
        # Restoring the provider does not bypass an open circuit's cooldown.
        return {'ok':True,'mode':body.mode,'circuit':application.state.routing_circuit.snapshot()}

    @application.patch('/api/shelters/{id}/occupancy')
    def occupancy(id:str,body:Occupancy,request:Request):
        sensor=request.headers.get('x-sensor-key','')
        configured=os.getenv('SENSOR_KEY','')
        if configured and secrets.compare_digest(sensor,configured):
            throttle('sensor:'+id,120);actor='sensor'
        else:actor=require(request,'shelter:write')['id']
        if body.source=='yolo' and body.coverage!='full':raise HTTPException(422,'partial_coverage_cannot_set_total_occupancy')
        now=time.time();observed=body.observed_at if body.observed_at is not None else now
        if observed>now+5 or observed<now-120:raise HTTPException(422,'stale_sensor_measurement')
        with store.lock,store.db:
            s=store.get('shelter',id)
            if not s:raise HTTPException(404,'not_found')
            if observed<s['observed_at']:raise HTTPException(409,'out_of_order_measurement')
            s.update(**body.model_dump(exclude={'observed_at'}),observed_at=observed)
            store.put('shelter',s);store.audit(actor,'occupancy.updated',id);store.evaluate()
        return s

    @application.patch('/api/roads/{id}')
    def road(id:str,body:Switch,request:Request):
        u=require(request,'road:write')
        with store.lock,store.db:
            r=store.get('road',id)
            if not r:raise HTTPException(404,'not_found')
            r['blocked']=body.enabled;store.put('road',r);store.audit(u['id'],'road.updated',id)
        return r

    @application.post('/api/alerts/{id}/{action}')
    def action(id:str,action:Literal['dispatch','open_shelter'],request:Request):
        u=require(request,'incident:act')
        try:return store.execute(id,action,u['id'])
        except ValueError as exc:raise HTTPException(409,str(exc))

    @application.patch('/api/teams/{id}')
    def team(id:str,body:TeamStatus,request:Request):
        u=require(request)
        if 'incident:act' not in u['permissions'] and not ('team:own' in u['permissions'] and u['team_id']==id):raise HTTPException(403,'permission_denied')
        with store.lock,store.db:
            t=store.get('team',id)
            if not t:raise HTTPException(404,'not_found')
            allowed={'available':set(),'en_route':{'on_scene'},'on_scene':{'available'}}
            if body.status not in allowed[t['status']]:raise HTTPException(409,'invalid_status_transition')
            t['status']=body.status
            if body.status=='available':t['incident_id']=None
            store.put('team',t);store.audit(u['id'],'team.status',id)
        return t

    @application.get('/api/roles')
    def roles(request:Request):require(request,'role:write');return store.objects('role')

    @application.post('/api/roles')
    def new_role(body:RoleBody,request:Request):
        u=require(request,'role:write')
        if any(p not in {p for ps in PERMISSIONS.values() for p in ps} for p in body.permissions):raise HTTPException(422,'unknown_permission')
        with store.lock,store.db:
            if store.get('role',body.name):raise HTTPException(409,'role_exists')
            store.put('role',{'id':body.name,'permissions':sorted(set(body.permissions))});store.audit(u['id'],'role.created',body.name)
        return {'ok':True}

    @application.get('/api/users')
    def users(request:Request):
        require(request,'role:write')
        with store.lock:return [dict(r) for r in store.db.execute('SELECT id,username,role,team_id FROM users ORDER BY username LIMIT 200')]

    @application.patch('/api/users/{id}/role')
    def assign_role(id:str,body:Assignment,request:Request):
        u=require(request,'role:write')
        with store.lock,store.db:
            if not store.get('role',body.role):raise HTTPException(404,'role_not_found')
            if body.team_id and not store.get('team',body.team_id):raise HTTPException(404,'team_not_found')
            if id==u['id']:raise HTTPException(409,'self_role_change_disabled')
            if not store.db.execute('SELECT id FROM users WHERE id=?',(id,)).fetchone():raise HTTPException(404,'user_not_found')
            store.db.execute('UPDATE users SET role=?,team_id=? WHERE id=?',(body.role,body.team_id,id));store.audit(u['id'],'user.role',id)
        return {'ok':True}

    @application.get('/api/audit')
    def audit(request:Request):
        require(request,'audit:read')
        with store.lock:return [dict(r) for r in store.db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]

    @application.post('/api/demo/{scenario}')
    def scenario(scenario:Literal['sos_wave','provider','websocket'],body:Switch,request:Request):
        u=require(request,'demo:write')
        if not demo:raise HTTPException(404,'not_found')
        with store.lock,store.db:
            if scenario=='sos_wave':
                for i in range(4):
                    user_id=uid();store.db.execute('INSERT INTO users VALUES(?,?,?,NULL,NULL)',(user_id,'simulation-'+user_id[:8],'citizen'))
                    store.report(user_id,uid(),'collapse',40.3725+i*.00003,49.8385+i*.00003)
            else:
                c=store.config();c[scenario+'_down']=body.enabled;store.put('config',c);store.audit(u['id'],'demo.failure',scenario)
        return {'ok':True}

    @application.websocket('/ws')
    async def ws(websocket:WebSocket):
        u=user_from(websocket.headers,websocket.cookies)
        if not u or not origin_ok(websocket.headers,websocket.url):await websocket.close(code=1008);return
        ok,_=limiter.allow('ws:'+u['id'],20,60)
        if not ok:await websocket.close(code=1013);return
        await websocket.accept()
        last=-1;last_sent=0
        try:
            while True:
                u=user_from(websocket.headers,websocket.cookies)
                if not u:await websocket.close(code=1008);break
                with store.lock:
                    if store.config()['websocket_down']:await websocket.close(code=1013);break
                    snapshot=store.snapshot(u)
                if snapshot['revision']!=last or time.monotonic()-last_sent>10:
                    await asyncio.wait_for(websocket.send_json({'type':'state','data':snapshot}),timeout=3)
                    last=snapshot['revision'];last_sent=time.monotonic()
                await asyncio.sleep(.5)
        except (WebSocketDisconnect,RuntimeError,asyncio.TimeoutError):pass

    @application.get('/')
    def index():return FileResponse(ROOT/'frontend/index.html')

    install_drills(application,store,require,user_from,origin_ok,throttle,demo)
    install_vision(application,vision_jobs,require,throttle,demo)
    application.mount('/',StaticFiles(directory=ROOT/'frontend',html=True),name='frontend')
    return application


app=create_app()
