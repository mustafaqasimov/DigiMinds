"""Small, deterministic geospatial primitives. All distances are meters."""
import heapq
import math


def distance(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    p1, p2 = map(math.radians, (lat1, lat2))
    h = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def shortest_path(nodes, edges, start, end):
    adj = {n['id']: [] for n in nodes}
    for e in edges:
        if not e['blocked']:
            adj[e['a']].append((e['b'], e['meters'], e['id']))
            adj[e['b']].append((e['a'], e['meters'], e['id']))
    queue, costs, previous = [(0, start)], {start: 0}, {}
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != costs[node]:
            continue
        if node == end:
            path, roads = [end], []
            while node != start:
                node, road = previous[node]
                path.append(node)
                roads.append(road)
            return {'nodes': list(reversed(path)), 'edges': list(reversed(roads)), 'meters': round(cost)}
        for nxt, weight, road in adj[node]:
            candidate = cost + weight
            if candidate < costs.get(nxt, math.inf):
                costs[nxt], previous[nxt] = candidate, (node, road)
                heapq.heappush(queue, (candidate, nxt))
    return None


def zone_for(lat, lng):
    return 'west' if lng < 49.842 else 'east'


def blocked_polygons(nodes, edges):
    lookup = {n['id']: n for n in nodes}
    polys = []
    for edge in edges:
        if edge['blocked']:
            a, b = lookup[edge['a']], lookup[edge['b']]
            west, east = min(a['lng'], b['lng'])-.00012, max(a['lng'], b['lng'])+.00012
            south, north = min(a['lat'], b['lat'])-.00009, max(a['lat'], b['lat'])+.00009
            polys.append([[[west,south],[east,south],[east,north],[west,north],[west,south]]])
    return polys


def segment_hits_box(a, b, box):
    """Slab test, including touching; coordinates are [lon, lat]."""
    lo, hi = 0., 1.
    for axis in (0, 1):
        lower, upper = min(p[axis] for p in box), max(p[axis] for p in box)
        delta = b[axis]-a[axis]
        if abs(delta) < 1e-14:
            if not lower <= a[axis] <= upper:
                return False
        else:
            t1, t2 = (lower-a[axis])/delta, (upper-a[axis])/delta
            lo, hi = max(lo, min(t1,t2)), min(hi, max(t1,t2))
            if lo > hi:
                return False
    return True


def crosses_closure(coords, polygons):
    return any(segment_hits_box(a,b,p[0]) for a,b in zip(coords,coords[1:]) for p in polygons)
