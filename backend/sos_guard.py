"""Cheap SOS admission before body parsing, the thread pool, and SQLite.

Single-process prototype: run one worker. No X-Forwarded-For trust is added here.
Only the server's configured/trusted ASGI peer address is used for IP quotas.
"""
import time
from collections import Counter
from starlette.requests import Request
from starlette.responses import JSONResponse
from .security import request_token


class SOSGuard:
    def __init__(self, app, limiter, tokens, max_active=16):
        self.app=app
        self.limiter=limiter
        self.tokens=tokens
        self.max_active=max_active
        self.active=0
        self.by_user=Counter()

    async def __call__(self,scope,receive,send):
        path=scope.get('path','').rstrip('/')
        parts=path.split('/')
        # Seismic help/trapped check-ins also create reports. Share admission
        # quotas with /api/sos so switching endpoints cannot bypass protection.
        intake=path=='/api/sos' or (len(parts)==5 and parts[1:3]==['api','seismic'] and parts[4]=='checkin')
        if scope['type']!='http' or scope['method']!='POST' or not intake:
            return await self.app(scope,receive,send)
        started=time.perf_counter()
        async def reject(status,detail,retry=None,quota=None):
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                     'Server-Timing':f'admission;dur={(time.perf_counter()-started)*1000:.2f}'}
            if retry is not None:headers['Retry-After']=str(retry)
            if quota:headers['X-RateLimit-Scope']=quota
            if status==401:headers['WWW-Authenticate']='Bearer'
            await JSONResponse({'detail':detail},status,headers=headers)(scope,receive,send)
        peer=(scope.get('client') or ('unknown',0))[0]
        ok,retry=self.limiter.allow('sos-ip:'+peer,1200,60)
        if not ok:return await reject(429,'rate_limited',retry,'ip')
        request=Request(scope)
        claims=self.tokens.verify(request_token(request.headers,request.cookies))
        if not claims:return await reject(401,'authentication_required')
        user_id=claims['sub']
        # Replays are bounded too, but do not consume the NEW report quota.
        ok,retry=self.limiter.allow('sos-traffic:'+user_id,60,60)
        if not ok:return await reject(429,'rate_limited',retry,'account')
        if self.active>=self.max_active or self.by_user[user_id]>=2:
            return await reject(429,'sos_busy',1,'concurrency')
        # No await between checking and reserving: atomic on this ASGI event loop.
        self.active+=1;self.by_user[user_id]+=1
        try:
            await self.app(scope,receive,send)
        finally:
            self.active-=1;self.by_user[user_id]-=1
            if not self.by_user[user_id]:del self.by_user[user_id]
