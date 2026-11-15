"""ASGI request bounds and response headers without a per-request task/stream bridge."""
import asyncio
import time
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import Response


class RequestGuards:
    def __init__(self,app,origin_ok,video_limit,voice_limit):
        self.app=app;self.origin_ok=origin_ok
        self.video_limit=video_limit;self.voice_limit=voice_limit

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        request=Request(scope);path=scope['path'];started=time.perf_counter()
        async def guarded_send(message):
            if message['type']=='http.response.start':
                headers=MutableHeaders(scope=message)
                headers['X-Content-Type-Options']='nosniff'
                headers['Referrer-Policy']='strict-origin-when-cross-origin'
                headers['X-Frame-Options']='DENY'
                headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; media-src 'self' blob:; connect-src 'self' ws: wss:; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
                headers['Server-Timing']=f'app;dur={(time.perf_counter()-started)*1000:.2f}'
                if path.startswith('/api'):headers['Cache-Control']='no-store'
                elif path=='/' or path.endswith(('.html','.js','.css')):headers['Cache-Control']='no-cache'
            await send(message)
        async def reject(detail,status):
            await Response(detail,status)(scope,receive,guarded_send)
        app_receive=receive
        if scope['method'] in ('POST','PUT','PATCH','DELETE'):
            if not self.origin_ok(request.headers,request.url):return await reject('Origin rejected',403)
            if not request.headers.get('authorization') and request.headers.get('x-requested-with')!='DigiMinds':
                return await reject('CSRF header required',403)
            try:declared=int(request.headers.get('content-length','0') or 0)
            except ValueError:return await reject('Invalid content length',400)
            if declared<0:return await reject('Invalid content length',400)
            video=scope['method']=='POST' and path=='/api/vision/jobs'
            voice=scope['method']=='POST' and path=='/api/voice/transcribe'
            limit=self.video_limit if video else self.voice_limit if voice else 65536
            if declared>limit:return await reject('Body too large',413)
            # Upload endpoints authenticate before consuming their bounded streams.
            if not (video or voice):
                chunks=[];size=0
                try:
                    async with asyncio.timeout(5):
                        while True:
                            message=await receive()
                            if message['type']=='http.disconnect':return
                            chunk=message.get('body',b'');size+=len(chunk)
                            if size>limit:return await reject('Body too large',413)
                            chunks.append(chunk)
                            if not message.get('more_body'):break
                except TimeoutError:return await reject('Body timeout',408)
                body=b''.join(chunks);consumed=False
                async def replay_receive():
                    nonlocal consumed
                    if not consumed:
                        consumed=True
                        return {'type':'http.request','body':body,'more_body':False}
                    return await receive()
                app_receive=replay_receive
        await self.app(scope,app_receive,guarded_send)
