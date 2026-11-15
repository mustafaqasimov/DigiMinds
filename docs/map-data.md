# Real basemap and offline coverage

The homepage and workspace now use Leaflet 1.9.4, vendored in `frontend/vendor` with its BSD-2-Clause license. There is no third-party JavaScript CDN dependency.

Online basemap: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, loaded only for visible map viewports. Browser HTTP caching is retained; there is no bulk download or offline tile prefetch. Attribution is visible. The CSP allows this exact image host; scripts stay self-hosted. Referrer policy is `strict-origin-when-cross-origin`.

Offline basemap: `frontend/baku.geojson` contains 6,156 real geographic features extracted from OpenStreetMap XML on 2026-11-15, covering central Baku around longitude 49.825–49.867 and latitude 40.359–40.385. Complete ways crossing the bounding box may extend beyond it. Features include streets, buildings, parks and the actual coastline. The water polygon closes outside the extract boundary. This is a finite city-centre extract, not a worldwide offline map.

Source: https://api.openstreetmap.org/api/0.6/map?bbox=49.825,40.359,49.867,40.385

© OpenStreetMap contributors. Data is available under the Open Database License (ODbL) 1.0: https://opendatacommons.org/licenses/odbl/1-0/ . Copyright and attribution: https://www.openstreetmap.org/copyright . The distributed GeoJSON is the extract used by the app. Rebuild with `python tools/build_offline_map.py /path/to/baku.osm`.

The service worker stores the extract and local application assets after a successful first online load. Selecting **Xəritə qatları → OpenStreetMap · Offline** removes the raster layer and uses the local extract. Browser connectivity loss or repeated tile failures also activates it. No tile provider API key is needed.

**Operational limit:** emergency events, shelter locations/capacities, teams and the existing local routing graph remain training data. Routes over the real basemap are explicitly simulated and drawn dashed. This change does not validate real evacuation corridors or certify shelters. RBAC, SOS deduplication and dispatch APIs are preserved.
