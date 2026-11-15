"""Pure geometry for person detections; no video or ML dependencies."""


def inside(point, polygon):
    x, y = point
    result = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            result = not result
        previous = current
    return result


def measure(boxes, polygon=None, area_m2=None):
    """Count one frame using bottom-center (ground contact) inside calibrated ROI.

    boxes contains xyxy person detections, never cumulative frame totals.
    area_m2 must describe the actual observed ground area, not image pixels.
    """
    if area_m2 is not None and area_m2 <= 0:
        raise ValueError('area_m2 must be positive')
    if polygon is not None and len(polygon) < 3:
        raise ValueError('polygon needs at least three vertices')
    count = sum(polygon is None or inside(((x1+x2)/2, y2), polygon)
                for x1, y1, x2, y2 in boxes)
    return {'count': count, 'density_people_m2': round(count/area_m2, 4) if area_m2 else None}
