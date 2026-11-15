"""600+ simultaneous real HTTP SOS requests, with dispatcher work during the burst.

Only disposable local fixtures are supported. Provisioning bypasses signup, never
JWT verification, SOS admission, deduplication, or role checks. Requires Node 20+.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import uvicorn
from backend.app import create_app
from backend.security import token_hash


def run_case(folder,scenario,requests,warm):
    app=create_app(str(Path(folder)/(scenario+'-'+str(warm)+'.db')),demo=True)
    store=app.state.store
    def provision(label,role):
        user={'id':label,'role':role}
        token,expiry=app.state.tokens.issue(user)
        store.db.execute('INSERT INTO users VALUES(?,?,?,NULL,NULL)',(label,label,role))
        store.db.execute('INSERT INTO sessions VALUES(?,?,?)',(token_hash(token),label,expiry))
        return token
    with store.lock,store.db:
        tokens=[provision('attacker-'+str(i),'citizen') for i in range(24)]
        operator=provision('operator','dispatcher');genuine=provision('genuine','citizen')
        for i in range(4):store.report('seed-'+str(i),'seed-key-'+str(i),'collapse',40.3725,49.8385)
        payload={'event_key':'original-replay-key','type':'collapse','lat':40.3725,'lng':49.8385}
        if scenario=='replay':store.report('attacker-0',**payload)
        alert=store.objects('alert')[0]['id']
        before=store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    sock=socket.socket();sock.bind(('127.0.0.1',0))
    base='http://127.0.0.1:'+str(sock.getsockname()[1])
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,backlog=2048,proxy_headers=False))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    try:
        deadline=time.monotonic()+10
        while not server.started and time.monotonic()<deadline:time.sleep(.01)
        if not server.started:raise RuntimeError('Fixture did not start')
        process=subprocess.run(['node',str(ROOT/'tools/flood_client.mjs')],input=json.dumps({'base_url':base,'tokens':tokens,'operator':operator,
            'genuine':genuine,'payload':payload,'alert':alert,'scenario':scenario,'requests':requests,'warm':warm}),text=True,capture_output=True,timeout=45)
        if process.returncode:raise RuntimeError(process.stderr)
        result=json.loads(process.stdout)
        after=store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
        result['new_reports']=after-before
        result['dispatch_actions']=store.db.execute("SELECT COUNT(*) FROM actions WHERE action='dispatch'").fetchone()[0]
        result['deduplication_pass']=(after-before==result['created'] and (after-before==1 if scenario=='replay' else after==before if scenario=='invalid' else after-before<=24))
        result['pass']=result['latency_pass'] and result['functionality_pass'] and result['deduplication_pass'] and result['dispatch_actions']==1
        return result
    finally:
        server.should_exit=True;thread.join(timeout=5);sock.close();store.db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests',type=int,default=600)
    parser.add_argument('--output')
    parser.add_argument('--scenario',choices=['all','replay','unique','invalid'],default='all')
    parser.add_argument('--cold',action='store_true',help='Include TCP connection establishment in timing')
    args=parser.parse_args()
    if not 501<=args.requests<=1000:parser.error('Use 501..1000 simultaneous requests')
    with tempfile.TemporaryDirectory() as folder:
        cases=[run_case(folder,s,args.requests,not args.cold) for s in (['replay','unique','invalid'] if args.scenario=='all' else [args.scenario])]
    result={'measured_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'python':platform.python_version(),
            'platform':platform.platform(),'logical_cpus':os.cpu_count(),'workers':1,'latency_target_mean_ms':300,'cases':cases,'pass':all(c['pass'] for c in cases)}
    text=json.dumps(result,indent=2);print(text)
    if args.output:Path(args.output).write_text(text+'\n')
    raise SystemExit(0 if result['pass'] else 1)
