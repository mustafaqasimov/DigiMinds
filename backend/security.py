import hashlib
import hmac
import secrets
import time
import heapq
import os
from pathlib import Path
from collections import OrderedDict, deque
from threading import Lock
import jwt

PERMISSIONS = {
    'citizen': ['sos:create','sos:own','route:read'],
    'priority_citizen': ['sos:create','sos:own','route:read'],
    'dispatcher': ['dashboard:read','incident:act','shelter:write','road:write','demo:write'],
    'responder': ['assignment:read','team:own'],
    'observer': ['dashboard:read'],
    'admin': ['dashboard:read','incident:act','shelter:write','road:write','demo:write','role:write','audit:read'],
}


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 240000).hex()
    return salt+':'+digest


def check_password(password, value):
    return hmac.compare_digest(password_hash(password, value.split(':')[0]), value)


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Limiter:
    """Thread-safe sliding windows; reject new keys at capacity, never evict live quotas."""
    def __init__(self, max_keys=20000, clock=time.monotonic):
        self.events = {}
        self.expiry = []
        self.lock = Lock()
        self.max_keys = max_keys
        self.clock = clock

    def allow(self, key, limit, window=60):
        now=self.clock()
        with self.lock:
            while self.expiry and self.expiry[0][0]<=now:
                _, expired_key = heapq.heappop(self.expiry)
                q, lifetime = self.events[expired_key]
                if q[-1]+lifetime<=now:
                    del self.events[expired_key]
                else:
                    heapq.heappush(self.expiry,(q[-1]+lifetime,expired_key))
            if key not in self.events:
                if len(self.events)>=self.max_keys:return False,1
                self.events[key]=(deque(),window)
                heapq.heappush(self.expiry,(now+window,key))
            q,_=self.events[key]
            while q and q[0]<=now-window: q.popleft()
            if len(q)>=limit: return False, max(1,int(window-(now-q[0]))+1)
            q.append(now)
            return True,0


class SessionTokens:
    """Signed JWTs plus the existing revocable server-side session registry.

    JWT role is descriptive. Permissions always come from the current DB role,
    so revocation and role demotion take effect on the next request.
    """
    issuer='digiminds'
    audience='crisis-api'
    lifetime=8*3600

    def __init__(self, db_path, demo):
        secret=os.getenv('JWT_SECRET','')
        if not secret and demo:
            if str(db_path)==':memory:':
                secret=secrets.token_urlsafe(48)
            else:
                path=Path(str(db_path)+'.jwt-key')
                try:
                    with open(path,'x',opener=lambda p,flags:os.open(p,flags,0o600)) as output:
                        secret=secrets.token_urlsafe(48);output.write(secret)
                except FileExistsError:
                    secret=path.read_text().strip()
        if len(secret.encode())<32:
            raise RuntimeError('JWT_SECRET must contain at least 32 bytes in production mode')
        self.secret=secret
        self.verified=OrderedDict()
        self.cache_lock=Lock()

    def issue(self, user):
        now=int(time.time())
        claims={'sub':user['id'],'role':user['role'],'jti':secrets.token_hex(16),
                'iss':self.issuer,'aud':self.audience,'iat':now,'nbf':now,'exp':now+self.lifetime}
        return jwt.encode(claims,self.secret,algorithm='HS256'),claims['exp']

    def verify(self, token):
        if not isinstance(token,str) or not 1<=len(token)<=4096:return None
        digest=token_hash(token);now=time.time()
        with self.cache_lock:
            cached=self.verified.get(digest)
            if cached and cached[0]>now:
                self.verified.move_to_end(digest)
                return dict(cached[1])
        try:
            claims=jwt.decode(token,self.secret,algorithms=['HS256'],issuer=self.issuer,audience=self.audience,
                options={'require':['sub','role','jti','iss','aud','iat','nbf','exp']})
            if not all(isinstance(claims[k],str) and claims[k] for k in ('sub','role','jti')):return None
            # Cache only signature/claim validation, NEVER session or role access.
            # user_from still checks revocation and current permissions in SQLite.
            with self.cache_lock:
                self.verified[digest]=(min(now+10,claims['exp']),dict(claims))
                self.verified.move_to_end(digest)
                while len(self.verified)>4096:self.verified.popitem(last=False)
            return claims
        except (jwt.InvalidTokenError,ValueError,TypeError):
            return None


def request_token(headers,cookies):
    # A malformed explicit Authorization header must not fall back to a cookie.
    bearer=headers.get('authorization')
    if bearer is not None:
        scheme,_,value=bearer.partition(' ')
        return value if scheme.lower()=='bearer' else ''
    return cookies.get('dm_session','')
