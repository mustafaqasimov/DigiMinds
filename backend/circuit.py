"""Per-process circuit breaker with bounded concurrency and one recovery probe."""
from dataclasses import dataclass
import math
import threading
import time


@dataclass(frozen=True)
class Permit:
    generation: int
    probe: bool


class CircuitBreaker:
    def __init__(self, failures=3, cooldown=30., max_in_flight=4, clock=time.monotonic):
        self.threshold=failures;self.cooldown=cooldown;self.max_in_flight=max_in_flight
        self.clock=clock;self.lock=threading.Lock();self.state='closed'
        self.failures=0;self.opened_until=0.;self.generation=0;self.in_flight=0
        self.calls=0;self.rejected=0;self.last_failure=None

    def acquire(self):
        with self.lock:
            if self.state=='open' and self.clock()>=self.opened_until:
                self.state='half_open'
                probe=True
            elif self.state in ('open','half_open'):
                self.rejected+=1
                return None, 'circuit_open' if self.state=='open' else 'recovery_probe_in_progress'
            else:probe=False
            if self.in_flight>=self.max_in_flight:
                if probe:self.state='open'
                self.rejected+=1
                return None,'provider_busy'
            self.in_flight+=1;self.calls+=1
            return Permit(self.generation,probe),None

    def finish(self, permit, success, reason=None):
        with self.lock:
            self.in_flight=max(0,self.in_flight-1)
            # In-flight successes from before the trip cannot close a newer circuit.
            if permit.generation!=self.generation:return
            if success is True:
                self.failures=0;self.last_failure=None;self.state='closed'
                if permit.probe:self.generation+=1
            elif success is False or permit.probe:
                self.failures+=1;self.last_failure=reason or 'cancelled_probe'
                if permit.probe or self.failures>=self.threshold:
                    self.state='open';self.opened_until=self.clock()+self.cooldown
                    self.generation+=1

    def snapshot(self):
        with self.lock:
            return {'state':self.state,'consecutive_failures':self.failures,
                    'retry_after_seconds':max(0,math.ceil(self.opened_until-self.clock())) if self.state=='open' else 0,
                    'in_flight':self.in_flight,'provider_calls':self.calls,
                    'short_circuited':self.rejected,'last_failure':self.last_failure}
