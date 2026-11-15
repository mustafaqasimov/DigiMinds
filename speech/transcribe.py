"""Isolated, bounded audio decoding and offline ASR; invoked by the web API."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .config import MODEL_DIR, MODEL_ID, MAX_SECONDS, model_ready
from .intent import classify, pace


class AudioError(ValueError):
    pass


def decode(path):
    import imageio_ffmpeg
    import numpy as np
    with Path(path).open('rb') as source:
        head = source.read(16)
    valid = ((head.startswith(b'RIFF') and head[8:12] == b'WAVE')
             or head.startswith((b'OggS', b'\x1aE\xdf\xa3', b'ID3', b'fLaC'))
             or head[4:8] == b'ftyp'
             or (len(head) > 1 and head[0] == 255 and head[1] & 224 == 224))
    if not valid:
        raise AudioError('voice_invalid_audio')
    # No URLs, playlists or network protocols, even inside a malicious container.
    result = subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-v', 'error',
        '-protocol_whitelist', 'file,pipe', '-threads', '1', '-i', str(path),
        '-map', '0:a:0', '-t', str(MAX_SECONDS + 1), '-vn', '-ac', '1', '-ar', '16000',
        '-f', 's16le', 'pipe:1'], capture_output=True, timeout=25)
    if result.returncode or len(result.stdout) < 12800:
        raise AudioError('voice_invalid_audio')
    audio = np.frombuffer(result.stdout, dtype='<i2').astype(np.float32) / 32768
    if len(audio) / 16000 > MAX_SECONDS + .5:
        raise AudioError('voice_too_long')
    return audio


def transcribe(path):
    import numpy as np
    from faster_whisper import WhisperModel
    started = time.monotonic()
    audio = decode(path)
    if not model_ready():
        raise AudioError('voice_not_installed')
    duration = len(audio) / 16000
    empty = {'text': '', 'suggested_type': None, 'candidates': [], 'ambiguous': False,
             'evidence': {}, 'duration_seconds': round(duration, 2), 'speech_seconds': 0,
             'words_per_minute': None, 'model': MODEL_ID, 'language': 'az',
             'warning': 'no_speech'}
    if float(np.sqrt(np.mean(audio ** 2))) < .001:
        return empty
    model = WhisperModel(str(MODEL_DIR), device='cpu', compute_type='int8',
                         cpu_threads=min(4, os.cpu_count() or 1), num_workers=1, local_files_only=True)
    segments, info = model.transcribe(audio, language='az', task='transcribe', beam_size=5,
                                     temperature=0, condition_on_previous_text=False,
                                     vad_filter=True, vad_parameters={'min_silence_duration_ms': 300},
                                     word_timestamps=True, hallucination_silence_threshold=1,
                                     compression_ratio_threshold=2.4, no_speech_threshold=.6)
    segments = list(segments)
    text = ' '.join(segment.text.strip() for segment in segments).strip()[:2000]
    if not text or info.duration_after_vad < .4:
        return empty
    words = [word for segment in segments for word in (segment.words or [])]
    confidence = sum(word.probability for word in words) / len(words) if words else 0
    uncertain = confidence < .5 or any(s.avg_logprob < -1 for s in segments)
    intent = classify(text)
    if uncertain:
        intent['suggested_type'] = None
    return {**intent, 'text': text, 'duration_seconds': round(duration, 2),
            'speech_seconds': round(info.duration_after_vad, 2),
            'words_per_minute': None if uncertain else pace(text, info.duration_after_vad),
            'language': 'az', 'model': MODEL_ID, 'warning': 'uncertain' if uncertain else None,
            'processing_seconds': round(time.monotonic() - started, 2)}


if __name__ == '__main__':
    os.environ['HF_HUB_OFFLINE'] = '1'
    folder = Path(sys.argv[1])
    try:
        result = transcribe(folder / 'input.audio')
    except AudioError as error:
        result = {'error': str(error)}
    except Exception:
        result = {'error': 'voice_failed'}
    # No transcript or raw audio goes to application logs.
    (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
