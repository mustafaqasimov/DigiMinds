# Reviewed sources and reuse

Reviewed 2026-11-15. Core application, map renderer, algorithms and tests were written for this repository. The project does not vendor another evacuation application's source.

| Source | Relevant idea / actual use |
| --- | --- |
| [JpCurada/likas](https://github.com/JpCurada/likas) | Evacuation destinations, hazard avoidance and local road graph. Routing source was inspected; this prototype implements its own Python/JS Dijkstra and applies our occupancy/closure rules. No LIKAS code copied. |
| [GIScience/openrouteservice](https://github.com/GIScience/openrouteservice) | Optional external foot-routing provider; closure polygons supplied using its API's avoid-polygons mechanism. ORS itself is not bundled or required. |
| [Ultralytics](https://github.com/ultralytics/ultralytics) | Installed optional YOLO dependency and YOLO11n weights for person detection. ROI/density and shelter publishing wrapper are this project's code. |
| [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) | Authenticated bidirectional transport; our app supplies role filtering and polling fallback. |

Primary API references: [ORS avoid polygons](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options), [Ultralytics prediction](https://docs.ultralytics.com/modes/predict/), [Ultralytics licensing](https://www.ultralytics.com/license).

Ultralytics is an optional third-party dependency with its own AGPL-3.0/Enterprise licensing choices; its model weights are not committed. The CPU smoke test used the official [bus image](https://github.com/ultralytics/assets/blob/main/im/bus.jpg), downloaded temporarily and not redistributed here. No camera feed or personal data is committed. FastAPI, HTTPX, Uvicorn, Pydantic and transitive dependencies retain their respective upstream licenses.
