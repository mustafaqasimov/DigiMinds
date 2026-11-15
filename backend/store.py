import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from .geo import distance, zone_for, shortest_path
from .seed import seed_map
from .security import PERMISSIONS


def uid(): return uuid.uuid4().hex


class Store:
    def __init__(self, path, clock=time.time):
        if path != ':memory:': Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db=sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self.lock=threading.RLock()
        self.clock=clock
        self.map=seed_map()
        self.revision=0
        self.db.executescript('''
          PRAGMA journal_mode=WAL;
          PRAGMA foreign_keys=ON;
          CREATE TABLE IF NOT EXISTS objects(kind TEXT,id TEXT,data TEXT,PRIMARY KEY(kind,id));
          CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE,role TEXT,password TEXT,team_id TEXT);
          CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expires REAL);
          CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY,type TEXT,lat REAL,lng REAL,zone TEXT,status TEXT,created REAL,updated REAL);
          CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,user_id TEXT,event_key TEXT,incident_id TEXT REFERENCES incidents(id),type TEXT,lat REAL,lng REAL,zone TEXT,created REAL,status TEXT,client_time REAL,UNIQUE(user_id,event_key));
          CREATE UNIQUE INDEX IF NOT EXISTS one_reporter_per_incident ON reports(user_id,incident_id);
          CREATE INDEX IF NOT EXISTS recent_reports ON reports(created,zone);
          CREATE TABLE IF NOT EXISTS actions(alert_id TEXT,action TEXT,resource TEXT,actor TEXT,created REAL,PRIMARY KEY(alert_id,action));
          CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT,action TEXT,target TEXT,created REAL);
        ''')
        with self.lock,self.db:
            if not self.objects('shelter'):
                for s in self.map['shelters']: self.put('shelter',{**s,'source':'simulation','observed_at':clock(),'coverage':'full'})
                for t in self.map['teams']: self.put('team',t)
                for r in self.map['roads']: self.put('road',r)
                for name,permissions in PERMISSIONS.items(): self.put('role',{'id':name,'permissions':permissions})
                self.put('config',{'id':'main','window_seconds':300,'radius_m':500,'sos_threshold':4,'reroute_percent':90,'critical_percent':95,'incident_radius_m':180,'provider_down':False,'websocket_down':False})

    def objects(self, kind):
        return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM objects WHERE kind=? ORDER BY id',(kind,))]

    def get(self, kind, id):
        r=self.db.execute('SELECT data FROM objects WHERE kind=? AND id=?',(kind,id)).fetchone()
        return json.loads(r[0]) if r else None

    def put(self, kind, obj):
        self.db.execute('INSERT OR REPLACE INTO objects VALUES(?,?,?)',(kind,obj['id'],json.dumps(obj)))

    def audit(self, actor, action, target):
        self.db.execute('INSERT INTO audit(actor,action,target,created) VALUES(?,?,?,?)',(actor,action,target,self.clock()))
        self.revision+=1

    def config(self): return self.get('config','main')

    def report(self, user_id, event_key, type, lat, lng, incident_id=None, client_time=None):
        with self.lock,self.db:
            old=self.db.execute('SELECT * FROM reports WHERE user_id=? AND event_key=?',(user_id,event_key)).fetchone()
            if old:
                if old['type']!=type or abs(old['lat']-lat)>.000001 or abs(old['lng']-lng)>.000001:
                    raise ValueError('idempotency_conflict')
                return dict(old),False
            now=self.clock(); cfg=self.config()
            candidates=self.db.execute("SELECT * FROM incidents WHERE type=? AND status!='resolved' AND updated>=? ORDER BY created,id",(type,now-1800)).fetchall()
            match=None
            for c in candidates:
                if incident_id and c['id']!=incident_id: continue
                if distance((lat,lng),(c['lat'],c['lng']))<=cfg['incident_radius_m']:
                    match=c;break
            if incident_id and not match: raise ValueError('incident_out_of_range')
            if match:
                iid=match['id']
                old=self.db.execute('SELECT * FROM reports WHERE user_id=? AND incident_id=?',(user_id,iid)).fetchone()
                if old:return dict(old),False
                self.db.execute('UPDATE incidents SET updated=? WHERE id=?',(now,iid))
            else:
                iid=uid()
                self.db.execute('INSERT INTO incidents VALUES(?,?,?,?,?,?,?,?)',(iid,type,lat,lng,zone_for(lat,lng),'open',now,now))
            r={'id':uid(),'user_id':user_id,'event_key':event_key,'incident_id':iid,'type':type,'lat':lat,'lng':lng,'zone':zone_for(lat,lng),'created':now,'status':'active','client_time':client_time}
            self.db.execute('INSERT INTO reports VALUES(:id,:user_id,:event_key,:incident_id,:type,:lat,:lng,:zone,:created,:status,:client_time)',r)
            self.audit(user_id,'sos.created',iid)
            self.evaluate()
            return r,True

    def safe(self,user_id):
        with self.lock,self.db:
            self.db.execute("UPDATE reports SET status='safe' WHERE user_id=? AND status='active'",(user_id,))
            self.audit(user_id,'citizen.safe',user_id)

    def evaluate(self):
        """Received-time sliding window; incident aggregation never removes reports.

        Zone OR anchored 500m circle. Circle centers are recent SOS coordinates.
        Deduplicate overlapping alert evidence; never use transitive DBSCAN chains.
        Old incident alerts remain in the audit trail when the trigger expires.
        """
        now=self.clock(); cfg=self.config()
        reports=[dict(r) for r in self.db.execute('SELECT * FROM reports WHERE created>=? AND created<=? ORDER BY created,id',(now-cfg['window_seconds'],now))]
        triggers=[]; zone_members={}
        def primary_incident(members):
            counts={}
            for member in members:
                counts[member['incident_id']]=counts.get(member['incident_id'],0)+1
            return max(counts,key=counts.get)
        for r in reports: zone_members.setdefault(r['zone'],[]).append(r)
        for zone, members in zone_members.items():
            if len(members)>=cfg['sos_threshold']:
                triggers.append(('zone:'+zone,'sos',primary_incident(members),{'rule':'zone','zone':zone,'count':len(members),'report_ids':[r['id'] for r in members],'types':sorted({r['type'] for r in members})}))
        covered=[set(t[3]['report_ids']) for t in triggers]
        # A single-zone circle is already covered by that zone's alert (or below
        # threshold). This keeps a mass report burst in one zone linear.
        for anchor in (reports if len(zone_members)>1 else []):
            members=[r for r in reports if distance((anchor['lat'],anchor['lng']),(r['lat'],r['lng']))<=cfg['radius_m']]
            ids={r['id'] for r in members}
            if len(ids)>=cfg['sos_threshold'] and not any(ids<=existing for existing in covered):
                triggers.append(('radius:'+anchor['incident_id'],'sos',anchor['incident_id'],{'rule':'radius','lat':anchor['lat'],'lng':anchor['lng'],'count':len(members),'report_ids':sorted(ids),'types':sorted({r['type'] for r in members})}))
                covered.append(ids)
        for s in self.objects('shelter'):
            if s['status']=='open' and s['occupancy']/s['capacity']*100>cfg['critical_percent']:
                triggers.append(('capacity:'+s['id'],'capacity',s['id'],{'percent':s['occupancy']/s['capacity']*100,'count':s['occupancy'],'capacity':s['capacity']}))
        existing={a['key']:a for a in self.objects('alert') if a['status']!='resolved'}
        active=set()
        for key,kind,target,evidence in triggers:
            active.add(key)
            a=dict(existing[key]) if key in existing else {'id':uid(),'key':key,'kind':kind,'target':target,'status':'open','created':now}
            a.update(evidence=evidence,condition_active=True)
            # Once dispatched, preserve the assignment target. Before dispatch,
            # follow the incident with the most reports in the rolling window.
            if a['status']=='open':a['target']=target
            if existing.get(key)!=a or key not in existing: self.revision+=1
            self.put('alert',a)
        for key,a in existing.items():
            if key not in active and a.get('condition_active'):
                a['condition_active']=False;self.put('alert',a);self.revision+=1

    def snapshot(self,user=None):
        with self.lock,self.db:
            self.evaluate()
            nodes=self.map['nodes'];lookup={n['id']:n for n in nodes}
            shelters=[]
            for s in self.objects('shelter'):
                shelters.append({**s,'lat':lookup[s['node']]['lat'],'lng':lookup[s['node']]['lng'],'percent':round(s['occupancy']/s['capacity']*100,2),'stale':self.clock()-s['observed_at']>300})
            incidents=[dict(r) for r in self.db.execute("SELECT i.*,COUNT(r.id) AS count,SUM(CASE WHEN r.status='active' THEN 1 ELSE 0 END) AS active_count FROM incidents i LEFT JOIN reports r ON r.incident_id=i.id GROUP BY i.id ORDER BY i.created DESC")]
            cfg=self.config()
            result={'revision':self.revision,'server_time':self.clock(),'map':{k:v for k,v in self.map.items() if k not in ('shelters','teams','roads')},'roads':self.objects('road'),'shelters':shelters,'incidents':incidents,'config':{k:v for k,v in cfg.items() if k not in ('provider_down','websocket_down')},'dataset':'SIMULATION'}
            permissions=user.get('permissions',[]) if user else []
            if 'dashboard:read' in permissions:
                result.update(teams=self.objects('team'),alerts=self.objects('alert'),reports=[dict(r) for r in self.db.execute('SELECT id,incident_id,type,lat,lng,zone,created,status FROM reports ORDER BY created DESC LIMIT 200')],failures={'provider':cfg['provider_down'],'websocket':cfg['websocket_down']})
            elif 'assignment:read' in permissions:
                result['teams']=[t for t in self.objects('team') if t['id']==user.get('team_id')]
                assigned={t.get('incident_id') for t in result['teams']}
                result['incidents']=[i for i in incidents if i['id'] in assigned]
            else:
                # Public maps do not expose individual SOS coordinates or identities.
                result['incidents']=[{k:v for k,v in x.items() if k in ('id','type','zone','count','active_count','status')} for x in incidents]
            if user:
                result['viewer']=user
                result['mine']=[dict(r) for r in self.db.execute('SELECT id,incident_id,type,status,created FROM reports WHERE user_id=? ORDER BY created DESC',(user['id'],))]
            result['stats']={'active_sos':sum(i['active_count'] or 0 for i in incidents),'incidents':len([i for i in incidents if i['status']!='resolved']),'open_shelters':sum(s['status']=='open' for s in shelters),'occupancy':sum(s['occupancy'] for s in shelters if s['status']=='open')}
            return result

    def local_routes(self, lat,lng):
        nodes=self.map['nodes']; roads=self.objects('road');cfg=self.config()
        start=min(nodes,key=lambda n:distance((lat,lng),(n['lat'],n['lng'])))
        snap=distance((lat,lng),(start['lat'],start['lng']))
        if snap>250: raise ValueError('outside_demo_area')
        lookup={n['id']:n for n in nodes};routes=[]
        for s in self.objects('shelter'):
            if s['status']!='open' or s['occupancy']/s['capacity']*100>=cfg['reroute_percent']: continue
            path=shortest_path(nodes,roads,start['id'],s['node'])
            if path:
                routes.append({**path,'shelter_id':s['id'],'shelter_name':s['name'],'source':'local_graph','minutes':round(path['meters']/75,1),'snap_meters':round(snap),'geometry':[[lookup[n]['lng'],lookup[n]['lat']] for n in path['nodes']],'observed_at':s['observed_at'],'stale':self.clock()-s['observed_at']>300})
        return sorted(routes,key=lambda r:r['meters'])

    def execute(self,alert_id,action,actor):
        with self.lock,self.db:
            old=self.db.execute('SELECT * FROM actions WHERE alert_id=? AND action=?',(alert_id,action)).fetchone()
            if old:return {**dict(old),'duplicate':True}
            a=self.get('alert',alert_id)
            if not a or a['status']=='resolved':raise ValueError('alert_unavailable')
            nodes=self.map['nodes'];roads=self.objects('road')
            if a['kind']=='capacity':
                target=self.get('shelter',a['target']);target_node=target['node'];needed=[]
            else:
                target=self.db.execute('SELECT * FROM incidents WHERE id=?',(a['target'],)).fetchone()
                target_node=min(nodes,key=lambda n:distance((target['lat'],target['lng']),(n['lat'],n['lng'])))['id'];needed=a['evidence'].get('types',[])
            if action=='dispatch':
                candidates=[]
                for team in self.objects('team'):
                    if team['status']!='available' or (needed and not any(x in team['skills'] for x in needed)):continue
                    route=shortest_path(nodes,roads,team['node'],target_node)
                    if route:candidates.append((route['meters'],team['id'],team))
                if not candidates:raise ValueError('no_available_team')
                _,_,resource=min(candidates,key=lambda t:(t[0],t[1]))
                resource.update(status='en_route',incident_id=a['target']);self.put('team',resource)
                if a['kind']=='sos':self.db.execute("UPDATE incidents SET status='responding' WHERE id=?",(a['target'],))
            elif action=='open_shelter':
                candidates=[]
                for s in self.objects('shelter'):
                    if s['status']!='standby':continue
                    route=shortest_path(nodes,roads,target_node,s['node'])
                    if route:candidates.append((route['meters'],s['id'],s))
                if not candidates:raise ValueError('no_reserve_shelter')
                _,_,resource=min(candidates,key=lambda t:(t[0],t[1]))
                resource.update(status='open',observed_at=self.clock());self.put('shelter',resource)
            else:raise ValueError('unknown_action')
            self.db.execute('INSERT INTO actions VALUES(?,?,?,?,?)',(alert_id,action,resource['id'],actor,self.clock()))
            a['status']='responding';self.put('alert',a);self.audit(actor,action,resource['id'])
            return {'alert_id':alert_id,'action':action,'resource':resource['id'],'duplicate':False}
