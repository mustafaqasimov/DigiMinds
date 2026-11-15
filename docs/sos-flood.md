# SOS flood challenge

## Implemented behavior

`POST /api/sos` and `POST /api/seismic/{id}/checkin` reject excess traffic before
reading their bodies or entering SQLite. Seismic help/trapped check-ins create
SOS reports, so they share the same admission and new-report quotas. Safe
check-ins consume traffic quota but do not consume new-report quota.
The admission middleware is a direct ASGI layer; it creates no task/stream bridge
for each rejected request. Normal input/CSRF/security-header checks are also ASGI.

| Protection | Default |
| --- | --- |
| IP traffic window | 1200 SOS requests / 60 seconds, including unauthenticated traffic |
| Account traffic window | 60 SOS requests / 60 seconds, including delivery retries |
| New delivery keys | 8 / account / 60 seconds, shared by that account's sessions |
| Accepted in-flight requests | 16 globally, at most 2 per account |
| SOS worker capacity | 4, separate from the default dispatcher worker pool |
| Ordinary request body | 64 KiB; maximum 5 seconds to receive it |
| Limiter memory | At most 20,000 keys; never evict a live quota to make room |

The IP threshold deliberately leaves room for users behind a shared NAT. Limits
are abuse/load controls, **not a classifier of truthful versus false reports**.
A real user can receive 429 during overload; it is not a successful SOS response.
The response includes `Retry-After`; manual sends and the existing offline queue
respect it. Admission 429 also exposes `X-RateLimit-Scope` (`ip`, `account`, or
`concurrency`). The launcher disables forwarded-header trust; a production reverse
proxy must explicitly overwrite forwarding headers and be configured as trusted.

## Duplicate handling

- `(user_id, event_key)` is scoped to the authenticated account.
- Reusing a key with changed incident type, coordinates, or an incompatible explicit
  incident ID produces 409 rather than a second report.
- Same user + same incident produces 200 and no `+1`, even with a new delivery key.
- A different user reporting that incident contributes one `+1`.
- `sos_deliveries` durably maps additional keys to the original report. Replaying
  an alias after restart or after the grouping window expires still returns the
  original report. It does not create a second incident.
- The quota check and deduplication run under the same database lock. SQLite
  uniqueness remains the final protection. Duplicates do not create audit floods.
- `X-SOS-Duplicate: true` identifies successful duplicate responses. Retries still
  count toward the traffic quota, so a known key is not an unlimited bypass.

## JWT and rescue permissions

Authentication issues HS256 JWTs with `sub`, `role`, `jti`, `iss`, `aud`, `iat`,
`nbf`, and `exp`. Algorithm, issuer (`digiminds`), audience (`crisis-api`), signature
and expiration are mandatory. `alg=none`, alternate algorithms, altered claims,
expired tokens, missing claims and unregistered sessions fail authentication.
See [PyJWT verification](https://pyjwt.readthedocs.io/en/stable/api.html).

The token hash must also exist in the server session registry. Logout revokes it
immediately. The current database role supplies permissions; an old JWT's `role`
claim cannot preserve privileges after demotion. A bounded 10-second cache stores
signature validation only, never authorization or session validity.

`POST /api/alerts/{id}/dispatch`, `/open_shelter`, and the combined `/respond`
action require `incident:act`.
Citizens, priority citizens, observers and responders cannot allocate teams.
Dispatcher/admin and explicitly delegated custom roles can. Assignment stays
atomic and idempotent, and actor/resource/action remain in the audit trail.

Production requires a random `JWT_SECRET` of at least 32 bytes; it must not be
committed. Demo mode generates a local `<database>.jwt-key` with restrictive file
permissions and ignores it in Git. Old opaque sessions require a new login after
this upgrade. Cookies stay HttpOnly/SameSite; production HTTPS uses SECURE_COOKIES=1.

## Reproduce the checks

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/*.test.mjs
python tools/load_test.py --isolated --requests 1000
python tools/flood_test.py --requests 600 --output flood-results.json
python tools/flood_test.py --requests 600 --cold --output flood-cold-results.json
```

The flood harness creates disposable SQLite databases and a real local Uvicorn
HTTP server. A separate Node client launches **600 concurrent SOS requests**;
no small client semaphore serializes them. During each burst it also sends 10
dashboard reads and 10 dispatch requests. Replay mode additionally sends one
legitimate user's SOS while the attack is in progress. The endpoint and all
admission/authentication checks are real; only test-account provisioning bypasses
the signup quota. Credentials go through stdin and are not written in reports.

Three scenarios: one account replays one key; 24 accounts submit fresh keys;
unauthenticated clients submit invalid tokens. We check expected HTTP statuses,
429 retry headers, exact report counts, one actual dispatch allocation, no 5xx,
and mean latency for SOS, **accepted SOS separately**, dispatcher reads and team
allocation. A fast 429 average cannot hide slow successful responses. The test
exits nonzero on functional failures or any measured group mean >=300 ms.

The normal-load script uses 8 concurrent requests (below admission capacity) to
check 24 new reports and 976 idempotent responses. It is complementary to the
600-concurrency overload test, not evidence of a 600-request burst by itself.
CI runs both and saves the flood JSON as an artifact.

Final regression verification: **182 Python tests passed, 2 skipped; 47 JavaScript tests passed**.

## Measurement boundaries

Default flood mode first establishes HTTP keep-alive connections, then measures
request start through full response reception. `--cold` also includes creating
600 TCP connections. `groups` are end-to-end client timings; `server_groups`
are separately reported `Server-Timing` measurements and must not be substituted
for end-to-end latency. Per-scenario p95 and max are retained in JSON.

The checked-in [measurement report](sos-flood-results.json) records the final
environment, both connection modes and pass/fail results. The final code includes
the concurrent capacity-response changes from `adbdfb7`. Client end-to-end results:

| Scenario, 600 concurrent SOS | SOS mean | Accepted SOS mean | Dashboard mean | Dispatch mean |
| --- | ---: | ---: | ---: | ---: |
| Repeated delivery, keep-alive | 98.82 ms | 209.42 ms | 188.74 ms | 175.53 ms |
| Fresh keys, 24 accounts, keep-alive | 215.27 ms | 429.82 ms | 364.22 ms | 360.45 ms |
| Invalid JWTs, keep-alive | 74.41 ms | No accepted SOS | 141.27 ms | 146.20 ms |

One legitimate SOS during the replay flood completed in 217.73 ms. All dispatcher
requests succeeded; repeated dispatches allocated only one team. Replays did not
create additional attacker reports; invalid tokens created none. Fresh-key
creation counts and 429/401 responses are checked against the database; no 5xx
responses occurred.

Creating all 600 TCP connections at once also exceeded the target: SOS means
were 250.70–335.99 ms, dispatch means 332.15–417.14 ms. Server-Timing values are
lower but are not substituted for client latency. Earlier runs, including a
passing keep-alive run before the capacity-response merge, are retained to show
runtime variability rather than selecting only favorable measurements.
**The unrestricted <300 ms requirement is not fully demonstrated.** This is not
an unconditional production latency guarantee. The strict flood command exits
nonzero on these latency failures; functional success does not override that.
Successful-request p95 can also exceed 300 ms even when the mean passes; this
requirement and test use the mean, not p95.

Run one application worker: SQLite and the limiter are process-local. Multi-worker
deployment needs a shared limiter and coordinated admission. These application
controls do not replace network-level protection against bandwidth/connection
exhaustion. Tests here cover the synthetic prototype dataset; deployment hardware,
large historical data, TLS and external network latency must be measured separately.
