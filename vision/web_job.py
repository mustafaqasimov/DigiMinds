"""Isolated video decoding/inference/encoding process for a single web upload."""
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

from .worker import build_parser, frame_record, render_preview

MAX_SECONDS = 60
MAX_FRAMES = 3600
MAX_PIXELS = 1920 * 1080


class VideoError(Exception):
    pass


def validate_container(path):
    with path.open('rb') as source:
        header = source.read(16)
    iso = len(header) >= 12 and header[4:8] in {b'ftyp', b'moov', b'mdat', b'wide', b'free'}
    avi = header[:4] == b'RIFF' and header[8:12] == b'AVI '
    webm = header[:4] == b'\x1a\x45\xdf\xa3'
    if not (iso or avi or webm):
        raise VideoError('vision_invalid_video')


def metadata(cap):
    import cv2
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if not cap.isOpened() or not all(math.isfinite(x) for x in (fps, frames)) or fps <= 0 or frames < 1:
        raise VideoError('vision_invalid_video')
    if width < 16 or height < 16 or width*height > MAX_PIXELS or max(width, height) > 1920:
        raise VideoError('vision_resolution_limit')
    if fps > 60 or frames > MAX_FRAMES or frames/fps > MAX_SECONDS+.05:
        raise VideoError('vision_duration_limit')
    return width, height, fps, int(frames)


def atomic_json(path, payload):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def analyze(folder):
    validate_container(folder/'input.video')
    # Uploaded media may never make the decoder fetch a remote URL/playlist.
    os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'protocol_whitelist;file,pipe'
    import cv2
    import imageio_ffmpeg
    import torch
    from ultralytics import YOLO

    started = time.monotonic()
    cap = cv2.VideoCapture(str(folder/'input.video'))
    encoder = None
    records = []
    try:
        width, height, fps, expected = metadata(cap)
        args = build_parser().parse_args(['--source', str(folder/'input.video'),
                                          '--model', os.getenv('VISION_MODEL_PATH', 'yolo26n.pt')])
        torch.set_num_threads(args.threads)
        atomic_json(folder/'status.json', {'state': 'loading', 'total_frames': expected,
                                          'duration_seconds': round(expected/fps, 2), 'progress': 0})
        model = YOLO(args.model)
        if model.task != 'detect' or model.names.get(0) != 'person':
            raise VideoError('vision_invalid_model')
        # Pad an odd dimension for H.264; never crop the user's image.
        out_width, out_height = width+(width % 2), height+68+((height+68) % 2)
        command = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
                   '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{out_width}x{out_height}',
                   '-r', str(fps), '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-preset', 'ultrafast',
                   '-crf', '23', '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                   str(folder/'result.mp4')]
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
        last_preview = float('-inf')
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if len(records) >= MAX_FRAMES or (len(records)+1)/fps > MAX_SECONDS+.05:
                raise VideoError('vision_duration_limit')
            if frame.shape[:2] != (height, width):
                raise VideoError('vision_invalid_video')
            result = model.predict(frame, classes=[0], conf=args.confidence, imgsz=args.imgsz,
                                   max_det=args.max_det, nms=True, iou=.7, device='cpu', verbose=False)[0]
            record = frame_record(result.boxes.xyxy.cpu().tolist(), args, None,
                                  len(records), time.time(), result.speed)
            records.append({'frame': record['frame'], 'time_seconds': round(record['frame']/fps, 3),
                            'count': record['count'], 'inference_ms': record['inference_ms'],
                            'warnings': record['warnings']})
            annotated = render_preview(result, None, record)
            annotated = cv2.copyMakeBorder(annotated, 0, out_height-annotated.shape[0],
                                          0, out_width-width, cv2.BORDER_CONSTANT)
            encoder.stdin.write(annotated.tobytes())
            now = time.monotonic()
            if now-last_preview > .7 or len(records) == expected:
                ok, jpeg = cv2.imencode('.jpg', annotated)
                if not ok:
                    raise VideoError('vision_failed')
                temp = folder/'preview.tmp'
                temp.write_bytes(jpeg.tobytes())
                temp.replace(folder/'preview.jpg')
                atomic_json(folder/'status.json', {
                    'state': 'processing', 'frames_processed': len(records),
                    'total_frames': expected, 'count': record['count'],
                    'progress': min(98, round(len(records)/expected*98)),
                    'elapsed_seconds': round(now-started, 1)})
                last_preview = now
        if not records or len(records) != expected:
            raise VideoError('vision_incomplete_video')
        atomic_json(folder/'status.json', {'state': 'encoding', 'frames_processed': len(records),
                                          'total_frames': expected, 'count': records[-1]['count'], 'progress': 99})
        encoder.stdin.close()
        if encoder.wait(timeout=60) != 0:
            raise VideoError('vision_encoding_failed')
        counts = [r['count'] for r in records]
        summary = {'model': Path(args.model).name, 'frames_processed': len(records),
                   'duration_seconds': round(len(records)/fps, 3), 'fps': fps,
                   'count_min': min(counts), 'count_max': max(counts),
                   'count_mean': round(statistics.mean(counts), 1), 'count_last': counts[-1],
                   'elapsed_seconds': round(time.monotonic()-started, 1),
                   'density_people_m2': None, 'warnings': sorted({w for r in records for w in r['warnings']})}
        atomic_json(folder/'report.json', {'summary': summary, 'frames': records,
                    'settings': {'confidence': args.confidence, 'imgsz': args.imgsz, 'device': 'cpu'},
                    'notes': ['Per-frame detections, not unique people or validated accuracy.',
                              'Physical area is unknown. Density is not calculated.',
                              'Output is silent and plays at the original video speed.']})
        atomic_json(folder/'status.json', {'state': 'completed', 'progress': 100,
                                          'frames_processed': len(records), 'total_frames': expected,
                                          'count': counts[-1], 'summary': summary})
    finally:
        cap.release()
        if encoder and encoder.poll() is None:
            encoder.kill()
            encoder.wait()


def main():
    folder = Path(sys.argv[1]).resolve()
    atomic_json(folder/'status.json', {'state': 'loading', 'progress': 0})
    try:
        analyze(folder)
    except Exception as error:
        code = str(error) if isinstance(error, VideoError) else 'vision_failed'
        atomic_json(folder/'status.json', {'state': 'failed', 'error': code})
        print(type(error).__name__+': '+str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
