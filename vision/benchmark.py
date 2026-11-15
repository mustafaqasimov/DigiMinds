"""Reproducible, local-video person detector comparison (no API publishing)."""
import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path


def run(args):
    import cv2
    import torch
    import ultralytics
    from ultralytics import YOLO

    source = Path(args.source)
    if not source.is_file():
        raise ValueError('Benchmark source must be a local video file')
    torch.set_num_threads(args.threads)
    capture = cv2.VideoCapture(str(source))
    frames = []
    index = 0
    while len(frames) < args.frames:
        ok, frame = capture.read()
        if not ok:
            break
        if index % args.stride == 0:
            frames.append((index, frame))
        index += 1
    capture.release()
    if not frames:
        raise ValueError('No readable frames')
    report = {'source': source.name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'ultralytics': ultralytics.__version__, 'torch': torch.__version__,
              'device': args.device, 'threads': args.threads, 'imgsz': args.imgsz,
              'confidence': args.confidence, 'iou': .7, 'max_det': 1000,
              'frame_indices': [i for i, _ in frames], 'models': [],
              'note': 'Unlabelled sample: detection counts are not accuracy scores. No physical area was supplied.'}
    for filename in args.models:
        model = YOLO(filename)
        if model.names.get(0) != 'person':
            raise ValueError('Expected COCO person class 0')
        options = dict(classes=[0], conf=args.confidence, iou=.7, imgsz=args.imgsz,
                       max_det=1000, nms=True, device=args.device, verbose=False)
        for _ in range(3):
            model.predict(frames[0][1], **options)
        counts, wall, inference = [], [], []
        for _, frame in frames:
            start = time.perf_counter()
            result = model.predict(frame, **options)[0]
            wall.append((time.perf_counter()-start)*1000)
            inference.append(result.speed['inference'])
            counts.append(len(result.boxes))
        values = {'model': Path(filename).name, 'frames': len(frames), 'counts': counts,
                  'count_min': min(counts), 'count_max': max(counts),
                  'count_mean': round(statistics.mean(counts), 2),
                  'wall_median_ms': round(statistics.median(wall), 2),
                  'inference_median_ms': round(statistics.median(inference), 2),
                  'processing_fps': round(len(wall)/(sum(wall)/1000), 2)}
        report['models'].append(values)
        print(json.dumps(values), flush=True)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--models', nargs='+', default=['yolo11n.pt', 'yolo26n.pt', 'yolo26s.pt'])
    parser.add_argument('--output', default='test-results/yolo26/benchmark.json')
    parser.add_argument('--frames', type=int, default=32)
    parser.add_argument('--stride', type=int, default=2)
    parser.add_argument('--imgsz', type=int, default=960)
    parser.add_argument('--confidence', type=float, default=.25)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--device', default='cpu')
    args = parser.parse_args()
    if not 1 <= args.frames <= 120 or args.stride < 1 or not 1 <= args.threads <= 32:
        parser.error('Use 1..120 frames, a positive stride, and 1..32 threads')
    if not 320 <= args.imgsz <= 2048 or not 0 < args.confidence <= 1:
        parser.error('Invalid image size or confidence')
    run(args)


if __name__ == '__main__':
    main()
