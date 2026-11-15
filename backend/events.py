"""Mass gatherings and their potential load on nearby assembly points (shelters).

Planning model, not a measurement: if an evacuation is needed while an event is
running, a share of the crowd walks to open shelters. Each shelter receives a
part inversely proportional to the squared walking distance (gravity model) on
the same road graph used for routing, so closed roads change the forecast.
Attendance follows a simple timeline: arrival ramps up 90 minutes before the
start, stays full during the event and drains 45 minutes after the end.
"""
import heapq
import math
import uuid

KINDS = ('concert', 'football', 'festival', 'rally', 'other')
ARRIVAL_S, DEPARTURE_S = 90 * 60, 45 * 60
REACH_M = 2000
PLACES = {  # Named spots on the synthetic training grid (see seed.py).
    'n6_4': 'Şimal Stadionu ətrafı', 'n3_5': 'Mərkəz Parkı meydanı', 'n1_6': 'Sahil bulvarı',
    'n4_2': 'Qərb meydanı', 'n2_4': 'Mərkəzi prospekt', 'n5_7': 'Şərq sərgi sahəsi',
}


def demo_events(now):
    """Synthetic events relative to `now`, so a fresh demo always has live and upcoming items."""
    hour = 3600
    return [
        {'id': 'ev-football', 'name': 'Futbol matçı', 'kind': 'football', 'node': 'n6_4',
         'attendance': 12000, 'start': now - 0.5 * hour, 'end': now + 1.25 * hour},
        {'id': 'ev-concert', 'name': 'Açıq hava konserti', 'kind': 'concert', 'node': 'n3_5',
         'attendance': 6000, 'start': now + 2 * hour, 'end': now + 5 * hour},
        {'id': 'ev-festival', 'name': 'Bulvar festivalı', 'kind': 'festival', 'node': 'n1_6',
         'attendance': 15000, 'start': now + 26 * hour, 'end': now + 32 * hour},
    ]


def new_id():
    return 'ev-' + uuid.uuid4().hex[:10]


def presence(event, now):
    """Share of expected attendance on site at `now`, and the event phase."""
    start, end = event['start'], event['end']
    if now < start - ARRIVAL_S:
        return 0., 'upcoming'
    if now < start:
        return (now - (start - ARRIVAL_S)) / ARRIVAL_S, 'arrival'
    if now <= end:
        return 1., 'live'
    if now < end + DEPARTURE_S:
        return 1 - (now - end) / DEPARTURE_S, 'departure'
    return 0., 'ended'


def walking_distances(nodes, roads, start):
    """Dijkstra from one node to every reachable node over open roads."""
    adj = {n['id']: [] for n in nodes}
    for r in roads:
        if not r['blocked']:
            adj[r['a']].append((r['b'], r['meters']))
            adj[r['b']].append((r['a'], r['meters']))
    dist, queue = {start: 0}, [(0, start)]
    while queue:
        d, node = heapq.heappop(queue)
        if d != dist[node]:
            continue
        for nxt, w in adj[node]:
            if d + w < dist.get(nxt, math.inf):
                dist[nxt] = d + w
                heapq.heappush(queue, (d + w, nxt))
    return dist


def level(percent, cfg):
    if percent > 100:
        return 'overflow'
    if percent >= cfg['reroute_percent']:
        return 'reroute'
    if percent >= 70:
        return 'watch'
    return 'ok'


def forecast(nodes, roads, shelters, events, cfg, now):
    """Per-event shelter load at the event's peak and now, plus the combined load now."""
    share = cfg.get('event_evac_share', .06)  # 6% of the crowd seeks an assembly point
    by_id = {s['id']: s for s in shelters}
    where = {n['id']: n for n in nodes}
    combined = {s['id']: 0. for s in shelters}
    results = []
    for ev in sorted(events, key=lambda e: e['start']):
        factor, phase = presence(ev, now)
        if phase == 'ended' and now - ev['end'] > 6 * 3600:
            continue
        dist = walking_distances(nodes, roads, ev['node'])
        reachable = [(s, dist[s['node']]) for s in shelters
                     if s['status'] == 'open' and s['node'] in dist and dist[s['node']] <= REACH_M]
        weights = {s['id']: 1 / (d + 150) ** 2 for s, d in reachable}
        total = sum(weights.values())
        seekers = ev['attendance'] * share
        rows = []
        for s, d in sorted(reachable, key=lambda x: x[1]):
            incoming = seekers * weights[s['id']] / total
            combined[s['id']] += incoming * factor
            peak = (s['occupancy'] + incoming) / s['capacity'] * 100
            rows.append({'id': s['id'], 'name': s['name'], 'meters': round(d), 'incoming': round(incoming),
                         'current_percent': round(s['occupancy'] / s['capacity'] * 100, 1),
                         'potential_percent': round(peak, 1), 'level': level(peak, cfg)})
        # Seats needed to keep every receiving shelter under the reroute threshold.
        deficit = round(sum(max(0, s['occupancy'] + r['incoming'] - s['capacity'] * cfg['reroute_percent'] / 100)
                            for r in rows for s in [by_id[r['id']]]))
        reserves = sorted((dist[s['node']], s) for s in shelters
                          if s['status'] == 'standby' and s['node'] in dist)
        reserve = reserves[0][1] if reserves and deficit > 0 else None
        unplaced = round(seekers) if not rows else 0
        results.append({**ev, 'lat': where[ev['node']]['lat'], 'lng': where[ev['node']]['lng'], 'phase': phase, 'presence': round(factor, 2), 'on_site': round(ev['attendance'] * factor),
                        'seekers': round(seekers), 'shelters': rows, 'deficit': deficit, 'unplaced': unplaced,
                        'worst': max((r['potential_percent'] for r in rows), default=None),
                        'reserve': {'id': reserve['id'], 'name': reserve['name'], 'capacity': reserve['capacity'],
                                    'meters': round(reserves[0][0])} if reserve else None})
    potential = {sid: round((by_id[sid]['occupancy'] + extra) / by_id[sid]['capacity'] * 100, 1)
                 for sid, extra in combined.items() if extra >= 1}
    return results, potential
