import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

PERMISSIONS = {
    'citizen': ['sos:create','sos:own','route:read'],
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
    """Bounded sliding-window limiter. Single-process prototype; Redis for replicas."""
    def __init__(self):
        self.events = defaultdict(deque)
        self.lock = Lock()

    def allow(self, key, limit, window=60):
        now=time.monotonic()
        with self.lock:
            if len(self.events)>20000:
                self.events={k:v for k,v in self.events.items() if v and v[-1]>now-3600}
                self.events=defaultdict(deque,self.events)
            q=self.events[key]
            while q and q[0]<=now-window: q.popleft()
            if len(q)>=limit: return False, max(1,int(window-(now-q[0]))+1)
            q.append(now)
            return True,0
