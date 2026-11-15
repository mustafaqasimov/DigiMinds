# Verification — 2026-11-15

## Automated

- Python 3.12.14: **33 tests passed** in 8.83 seconds.
- Node 24.22.1: **3 offline-routing tests passed**.
- Tests cover rolling-window boundaries, zone/radius OR semantics, 90% and strictly-over-95% thresholds, fixed-anchor grouping, separate emergency types, reporter deduplication, conflicting idempotency keys, blocked/unreachable roads, external-provider fallback and state-change races, atomic/idempotent dispatch, unavailable resources, RBAC and custom roles, public/responder privacy, CSRF, body limits, throttling, authenticated WebSockets, sensor freshness/coverage, persistence, safe status and citizen-session restoration.
- Mass integration scenario: **200 distinct citizen identities**, concurrency 40, then 200 replay deliveries. Exactly 200 reports and one incident with count 200; no replay inflation.
- Upstream test-client deprecation warnings were emitted; they did not affect the test results.

## Real HTTP load fixture

Command: `python tools/load_test.py --isolated`. Temporary SQLite database and a real local Uvicorn TCP listener, not a mocked HTTP transport. Measurement from this shared development environment:

| Metric | Observed |
| --- | ---: |
| Deliveries | 1,000 |
| Distinct citizens | 24 |
| Concurrency | 40 |
| Elapsed | 8.016 s |
| Throughput | 124.7 requests/s |
| Median | 244.43 ms |
| p95 | 779.39 ms |
| p99 | 1,148.32 ms |
| HTTP 201 | 24 |
| HTTP 200 (deduplicated) | 976 |
| Errors in delivery burst | 0 |

A subsequent fresh-key flood from one identity correctly received `429` and `Retry-After`. The 1,000-delivery test measures retry-heavy load; it is not a claim of 1,000 unique new citizens or production capacity. The separate 200-identity test covers unique report creation.

## YOLO CPU smoke test

Ultralytics 8.4.213, YOLO11n weights, CPU, confidence 0.35. Official Ultralytics `bus.jpg` sample produced **4 person detections**. Worker output was partial coverage and unpublished; no invented physical area or density was used. Geometry tests separately check ROI ground contact, calibrated density and no accumulation across frames. This verifies actual inference, not accuracy on a local shelter CCTV dataset. No real camera/RTSP stream was supplied.

## Browser observations

Verified in the live Chromium preview:

- Citizen sends collapse SOS; repeating `+1` from the same identity leaves count 1.
- Four additional simulated reports produce a red zone alert and grouped incident count 4.
- Dispatch changes one team from available to en route; reserve-site action increases open shelters from 4 to 5.
- Stopped the backend preview and reloaded: Service Worker still opened the app/map and browser routing produced the 574 m route.
- Medical SOS during that outage was visibly marked **unsent** in IndexedDB. After restart and return to the original citizen session, the queue cleared and the medical report appeared once.
- “I am safe” changed own active reports to safe; English language switching updated operational controls.
- WebSocket failure injection changed the status badge to Polling fallback while operational data remained available.

## Verification limits

The map is synthetic. Real OSM import, surveyed shelter capacities, production authentication, physical dispatch integration and real CCTV calibration remain outside this prototype. No external routing API key was supplied: provider fallback/race behavior was tested, but a live authenticated OpenRouteService response was not. Mobile CSS is included, but this run did not perform a physical-device or screen-reader audit. Load numbers are a single-machine development measurement, not an SLA.
