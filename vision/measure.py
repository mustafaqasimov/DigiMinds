"""Pure geometry for per-frame person detections; no video/ML dependencies."""
import math


def inside(point, polygon):
    """Include the polygon boundary, so edge detections are counted consistently."""
    x, y = point
    result = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        cross = (x-x1)*(y2-y1)-(y-y1)*(x2-x1)
        if abs(cross) <= 1e-7 and min(x1,x2) <= x <= max(x1,x2) and min(y1,y2) <= y <= max(y1,y2):
            return True
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            result = not result
        previous = current
    return result


def measure(boxes, polygon=None, area_m2=None):
    """Count bottom-center ground contact in ROI; area is measured ground m²."""
    if area_m2 is not None and (not math.isfinite(area_m2) or area_m2 <= 0):
        raise ValueError('area_m2 must be finite and positive')
    if polygon is not None:
        if not isinstance(polygon, (list, tuple)) or len(polygon) < 3:
            raise ValueError('polygon needs at least three vertices')
        if any(not isinstance(p, (list, tuple)) or len(p) != 2 or
               any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in p) for p in polygon):
            raise ValueError('polygon vertices must be finite x/y pairs')
        twice_area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(polygon, polygon[1:]+polygon[:1]))
        if abs(twice_area) < 1e-7:
            raise ValueError('polygon must enclose a nonzero area')
    count = sum(polygon is None or inside(((x1+x2)/2, y2), polygon)
                for x1, y1, x2, y2 in boxes)
    return {'count': count, 'density_people_m2': round(count/area_m2, 4) if area_m2 is not None else None}
