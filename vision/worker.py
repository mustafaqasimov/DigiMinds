"""Run a local YOLO sensor: python -m vision.worker --help.

Partial views are measurements, never silently promoted to shelter occupancy.
Publish only after confirming that the view covers the whole occupied area.
"""
import argparse
import json
import os
import time
from pathlib import Path
from .measure import measure


def run(args):
    import httpx
    from ultralytics import YOLO

    if args.publish and (args.coverage != 'full' or not os.getenv('SENSOR_KEY')):
        raise SystemExit('Publishing requires --coverage full and the SENSOR_KEY environment variable')
    if args.publish and not args.shelter:
        raise SystemExit('--shelter is required for publishing')
    polygon = json.loads(Path(args.roi).read_text()) if args.roi else None
    model = YOLO(args.model)
    source = int(args.source) if args.source.isdigit() else args.source
    last_send = 0
    client = httpx.Client(timeout=4) if args.publish else None
    try:
        for index, result in enumerate(model.predict(source=source, stream=True, classes=[0],
                                                     conf=args.confidence, device=args.device,
                                                     verbose=False)):
            measurement = measure(result.boxes.xyxy.cpu().tolist(), polygon, args.area_m2)
            now = time.time()
            record = {**measurement, 'frame': index, 'observed_at': now,
                      'source': 'yolo', 'coverage': args.coverage, 'published': False}
            if args.publish and now-last_send >= args.interval:
                try:
                    response = client.patch(f'{args.api.rstrip("/")}/api/shelters/{args.shelter}/occupancy',
                        headers={'X-Sensor-Key': os.environ['SENSOR_KEY'], 'X-Requested-With': 'DigiMinds'},
                        json={'occupancy': measurement['count'], 'source': 'yolo',
                              'observed_at': now, 'coverage': 'full',
                              'density_people_m2': measurement['density_people_m2']})
                    response.raise_for_status()
                    record['published'] = True
                except httpx.HTTPError as exc:
                    record['publish_error'] = type(exc).__name__
                last_send = now
            print(json.dumps(record), flush=True)
            if args.max_frames and index+1 >= args.max_frames:
                break
    finally:
        if client:
            client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Local image/video, camera index or authorized RTSP URL')
    parser.add_argument('--model', default='yolo11n.pt', help='Pre-download weights for offline inference')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--confidence', type=float, default=.35)
    parser.add_argument('--roi', help='JSON polygon in source-image pixel coordinates')
    parser.add_argument('--area-m2', type=float, help='Calibrated physical area visible inside ROI')
    parser.add_argument('--coverage', choices=['partial', 'full'], default='partial')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--shelter')
    parser.add_argument('--api', default='http://127.0.0.1:3000')
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--max-frames', type=int, default=0)
    arguments = parser.parse_args()
    if not 0 < arguments.confidence <= 1 or arguments.interval <= 0 or arguments.max_frames < 0:
        parser.error('Invalid confidence, interval or frame limit')
    run(arguments)
