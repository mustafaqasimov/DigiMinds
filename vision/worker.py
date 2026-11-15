"""Local YOLO26 person sensor: python -m vision.worker --help.

Counts are per-frame estimates, never accumulated across frames. Only a full
view with no detection-cap warning may update shelter occupancy.
"""
import argparse
import json
import math
import os
import time
from pathlib import Path
from .measure import measure, inside

DEFAULT_MODEL = 'yolo26n.pt'


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Local image/video, camera index or authorized RTSP URL')
    parser.add_argument('--model', default=DEFAULT_MODEL, help='YOLO26n by default; choose another YOLO26 scale for your camera benchmark')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--threads', type=int, default=4, help='PyTorch CPU threads')
    parser.add_argument('--confidence', type=float, default=.25)
    parser.add_argument('--imgsz', type=int, default=960, help='960 by default; 640 for speed or 1280 for a high-resolution camera')
    parser.add_argument('--max-det', type=int, default=1000, help='Detection cap; reaching it blocks occupancy publishing')
    parser.add_argument('--vid-stride', type=int, default=1, help='Process every Nth video frame')
    parser.add_argument('--roi', help='JSON polygon in source-image pixel coordinates')
    parser.add_argument('--area-m2', type=float, help='Measured ground area of the ROI (or whole view if no ROI)')
    parser.add_argument('--coverage', choices=['partial', 'full'], default='partial')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--shelter')
    parser.add_argument('--api', default='http://127.0.0.1:3000')
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--max-frames', type=int, default=0)
    parser.add_argument('--save-preview', help='Write the latest annotated .jpg/.png at the interval, plus the first/last frame')
    return parser


def validate_args(args):
    if not math.isfinite(args.confidence) or not 0 < args.confidence <= 1:
        raise ValueError('Confidence must be in (0, 1]')
    if not math.isfinite(args.interval) or args.interval <= 0 or args.max_frames < 0:
        raise ValueError('Invalid interval or frame limit')
    if not 320 <= args.imgsz <= 2048 or not 1 <= args.max_det <= 5000 or args.vid_stride < 1 or not 1 <= args.threads <= 32:
        raise ValueError('Invalid image size, detection cap or video stride')
    if args.save_preview and Path(args.save_preview).suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
        raise ValueError('Preview must be a .jpg/.jpeg/.png path')
    if args.publish and (args.coverage != 'full' or not os.getenv('SENSOR_KEY')):
        raise ValueError('Publishing requires --coverage full and SENSOR_KEY in the environment')
    if args.publish and not args.shelter:
        raise ValueError('--shelter is required for publishing')
    polygon = json.loads(Path(args.roi).read_text()) if args.roi else None
    measure([], polygon, args.area_m2)  # Validate calibration before loading PyTorch or weights.
    return polygon


def frame_record(boxes, args, polygon, index, observed_at, speed=None):
    measurement = measure(boxes, polygon, args.area_m2)
    capped = len(boxes) >= args.max_det
    return {**measurement, 'frame': index, 'observed_at': observed_at,
            'source': 'yolo', 'model': Path(args.model).name,
            'coverage': args.coverage, 'published': False,
            'detected_in_frame': len(boxes), 'detection_limit_reached': capped,
            'area_m2': args.area_m2, 'imgsz': args.imgsz,
            'inference_ms': round((speed or {}).get('inference', 0), 2),
            'warnings': ['detection_limit_reached_count_is_lower_bound'] if capped else []}


def publish_measurement(client, args, record):
    import httpx
    if record['detection_limit_reached']:
        record['publish_error'] = 'detection_limit_reached'
        return
    try:
        response = client.patch(f'{args.api.rstrip("/")}/api/shelters/{args.shelter}/occupancy',
            headers={'X-Sensor-Key': os.environ['SENSOR_KEY'], 'X-Requested-With': 'DigiMinds'},
            json={'occupancy': record['count'], 'source': 'yolo',
                  'observed_at': record['observed_at'], 'coverage': args.coverage,
                  'density_people_m2': record['density_people_m2']})
        response.raise_for_status()
        record['published'] = True
    except httpx.HTTPError as exc:
        record['publish_error'] = type(exc).__name__


def render_preview(result, polygon, record):
    import cv2
    import numpy as np
    frame = result.orig_img.copy()
    for box in result.boxes.xyxy.cpu().tolist():
        x1, y1, x2, y2 = box
        selected = polygon is None or inside(((x1+x2)/2, y2), polygon)
        color = (0, 121, 255) if selected else (150, 150, 150)
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        cv2.circle(frame, (int((x1+x2)/2), int(y2)), 3, color, -1)
    if polygon:
        cv2.polylines(frame, [np.array(polygon, dtype=np.int32)], True, (60, 200, 80), 2)
    density = 'uncalibrated' if record['density_people_m2'] is None else f"{record['density_people_m2']:.3f} people/m2"
    banner = np.full((68, frame.shape[1], 3), (57, 44, 24), dtype=np.uint8)
    cv2.putText(banner, f"{record['model']}  |  People in view/ROI: {record['count']}", (12, 26), cv2.FONT_HERSHEY_SIMPLEX, .56, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(banner, f"Density: {density}  |  {record['coverage']} view", (12, 51), cv2.FONT_HERSHEY_SIMPLEX, .46, (220, 225, 230), 1, cv2.LINE_AA)
    return np.concatenate([banner, frame])


def save_preview(result, polygon, record, filename):
    import cv2
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), render_preview(result, polygon, record)):
        raise OSError('Could not save preview')


def run(args):
    polygon = validate_args(args)
    import httpx
    from ultralytics import YOLO
    import torch

    torch.set_num_threads(args.threads)
    model = YOLO(args.model)
    if model.task != 'detect' or model.names.get(0) != 'person':
        raise ValueError('Use a COCO person detection model (class 0 must be person)')
    source = int(args.source) if args.source.isdigit() else args.source
    last_send = last_preview = float('-inf')
    client = httpx.Client(timeout=4) if args.publish else None
    results = model.predict(source=source, stream=True, classes=[0], conf=args.confidence,
                            imgsz=args.imgsz, max_det=args.max_det, nms=True, iou=.7,
                            vid_stride=args.vid_stride, stream_buffer=False,
                            device=args.device, verbose=False)
    last_result = last_record = None
    try:
        for index, result in enumerate(results):
            height, width = result.orig_shape
            if polygon and any(not (0 <= x <= width and 0 <= y <= height) for x, y in polygon):
                raise ValueError('ROI extends beyond the source frame; use source-image pixels')
            record = frame_record(result.boxes.xyxy.cpu().tolist(), args, polygon,
                                  index, time.time(), result.speed)
            now = time.monotonic()
            if client is not None and now-last_send >= args.interval:
                publish_measurement(client, args, record)
                last_send = now
            if args.save_preview and now-last_preview >= args.interval:
                save_preview(result, polygon, record, args.save_preview)
                last_preview = now
            print(json.dumps(record, allow_nan=False), flush=True)
            last_result, last_record = result, record
            if args.max_frames and index+1 >= args.max_frames:
                break
        if args.save_preview and last_result is not None:
            save_preview(last_result, polygon, last_record, args.save_preview)
    finally:
        results.close()
        if client:
            client.close()


if __name__ == '__main__':
    parser = build_parser()
    arguments = parser.parse_args()
    try:
        run(arguments)
    except (ValueError, OSError) as error:
        parser.exit(2, f'YOLO sensor: {error}\n')
