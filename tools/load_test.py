"""Live HTTP burst: many citizens, repeated delivery, grouping, rate limiting.

Start an isolated demo server, then python tools/load_test.py --base-url URL.
Creates test SOS data. Never run against a real response system.
"""
import argparse
import asyncio
import collections
import json
import math
import statistics
import time
import uuid
import socket
import sys
import tempfile
import threading
from pathlib import Path
import httpx

async def run(args):
    semaphore=asyncio.Semaphore(args.concurrency)
    clients=[];events=[];latencies=[];counts=collections.Counter()
    async with httpx.AsyncClient(base_url=args.base_url,timeout=30,limits=httpx.Limits(max_connections=args.concurrency)) as client:
        health=(await client.get('/api/health')).json()
        if not health.get('demo'):raise RuntimeError('Load generator requires an explicit demo server')
        for i in range(args.users):
            response=await client.post('/api/auth/guest',headers={'X-Requested-With':'DigiMinds','Cookie':''})
            response.raise_for_status();clients.append(response.json()['token'])
            events.append({'event_key':str(uuid.uuid4()),'type':'collapse','lat':40.3725+(i%4)*.00001,'lng':49.8385})
        async def send(i):
            async with semaphore:
                who=i%args.users;start=time.perf_counter()
                r=await client.post('/api/sos',headers={'Authorization':'Bearer '+clients[who]},json=events[who])
                latencies.append((time.perf_counter()-start)*1000);counts[r.status_code]+=1
        start=time.perf_counter();await asyncio.gather(*(send(i) for i in range(args.requests)));elapsed=time.perf_counter()-start
        # One identity sending fresh requests must hit the SOS limit.
        rate_responses=[]
        for _ in range(12):
            r=await client.post('/api/sos',headers={'Authorization':'Bearer '+clients[0]},json={**events[0],'event_key':str(uuid.uuid4())})
            rate_responses.append(r.status_code)
        ordered=sorted(latencies)
        result={'requests':args.requests,'distinct_citizens':args.users,'concurrency':args.concurrency,'elapsed_seconds':round(elapsed,3),'throughput_rps':round(args.requests/elapsed,1),'p50_ms':round(statistics.median(latencies),2),'p95_ms':round(ordered[math.ceil(len(ordered)*.95)-1],2),'p99_ms':round(ordered[math.ceil(len(ordered)*.99)-1],2),'http_statuses':dict(counts),'rate_limit_verified':429 in rate_responses,'one_creation_per_citizen':counts[201]==args.users,'errors':sum(v for k,v in counts.items() if k>=400)}
        print(json.dumps(result,indent=2))
        if args.output:Path(args.output).write_text(json.dumps(result,indent=2))
        if result['errors'] or not result['rate_limit_verified'] or not result['one_creation_per_citizen']:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:3000');p.add_argument('--users',type=int,default=24);p.add_argument('--requests',type=int,default=1000);p.add_argument('--concurrency',type=int,default=8);p.add_argument('--output')
    p.add_argument('--isolated',action='store_true',help='Use a disposable local HTTP test fixture; do not alter demo data')
    args=p.parse_args()
    if not 1<=args.users<=32 or args.requests<args.users or args.concurrency<1:
        p.error('Use 1..32 citizens, requests >= citizens and positive concurrency')
    if args.isolated:
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
        import uvicorn
        from backend.app import create_app
        with tempfile.TemporaryDirectory() as folder:
            fixture=create_app(str(Path(folder)/'load.db'),demo=True)
            sock=socket.socket();sock.bind(('127.0.0.1',0))
            args.base_url='http://127.0.0.1:'+str(sock.getsockname()[1])
            server=uvicorn.Server(uvicorn.Config(fixture,log_level='error'))
            thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
            deadline=time.monotonic()+10
            while not server.started and time.monotonic()<deadline:time.sleep(.01)
            if not server.started:raise RuntimeError('Test fixture did not start')
            try:asyncio.run(run(args))
            finally:
                server.should_exit=True;thread.join(timeout=5);sock.close();fixture.state.store.db.close()
    else:asyncio.run(run(args))
