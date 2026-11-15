"""Authenticated, bounded voice transcription. No audio retained after a request."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from uuid import uuid4

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from speech.config import MAX_UPLOAD, MAX_SECONDS, MODEL_ID, model_ready
from speech.intent import classify
from .vision_jobs import terminate_tree

TIMEOUT = 150


class VoiceNote(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    text: str = Field(min_length=1, max_length=2000)
    speech_seconds: float | None = Field(default=None, ge=0, le=21)
    words_per_minute: int | None = Field(default=None, ge=0, le=2000)
    suggested_type: Literal['fire', 'collapse', 'flood', 'medical'] | None = None


class VoiceText(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(max_length=2000)


def available():
    return (all(importlib.util.find_spec(name) for name in ('faster_whisper', 'imageio_ffmpeg'))
            and model_ready())


class VoiceService:
    def __init__(self, root, directory):
        self.root, self.directory = Path(root), Path(directory)
        self.lock = threading.Lock()
        self.active = False
        self.closed = False
        self.process = None
        if self.directory.is_dir():
            for path in self.directory.iterdir():
                if path.is_dir() and re.fullmatch(r'[a-f0-9]{32}', path.name):
                    shutil.rmtree(path, ignore_errors=True)

    def reserve(self):
        with self.lock:
            if self.closed or self.active:
                raise HTTPException(409, 'voice_busy')
            folder = self.directory / uuid4().hex
            folder.mkdir(parents=True, mode=0o700)
            self.active = True
            return folder

    async def execute(self, folder, request):
        with self.lock:
            if self.closed:
                raise HTTPException(503, 'voice_unavailable')
            process = subprocess.Popen([sys.executable, '-m', 'speech.transcribe', str(folder)],
                cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=os.name != 'nt',
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
            self.process = process
        try:
            deadline = time.monotonic() + TIMEOUT
            while process.poll() is None:
                if self.closed or await request.is_disconnected():
                    raise HTTPException(408, 'voice_cancelled')
                if time.monotonic() > deadline:
                    raise HTTPException(504, 'voice_timeout')
                await asyncio.sleep(.15)
            result_file = folder / 'result.json'
            if process.returncode or not result_file.is_file() or result_file.stat().st_size > 32768:
                raise HTTPException(500, 'voice_failed')
            result = json.loads(result_file.read_text(encoding='utf-8'))
            if result.get('error'):
                error = result['error']
                raise HTTPException(422 if error in {'voice_invalid_audio', 'voice_too_long'} else 503, error)
            return result
        finally:
            terminate_tree(process)
            with self.lock:
                self.process = None

    def release(self, folder):
        shutil.rmtree(folder, ignore_errors=True)
        with self.lock:
            self.active = False

    def close(self):
        with self.lock:
            self.closed = True
            process = self.process
        terminate_tree(process)


def install_voice(app, manager, require, throttle):
    @app.get('/api/voice/status')
    def status():
        return {'available': available(), 'model': MODEL_ID, 'language': 'az',
                'max_seconds': MAX_SECONDS, 'max_upload_bytes': MAX_UPLOAD}

    @app.post('/api/voice/classify')
    def text_intent(body: VoiceText, request: Request):
        user = require(request, 'sos:create')
        throttle('voice-text:' + user['id'], 30)
        return classify(body.text)

    @app.post('/api/voice/transcribe')
    async def upload(request: Request):
        user = require(request, 'sos:create')
        throttle('voice:' + user['id'], 8)
        if not available():
            raise HTTPException(503, 'voice_not_installed')
        mime = request.headers.get('content-type', '').split(';')[0].lower()
        if mime not in {'audio/webm', 'audio/ogg', 'audio/wav', 'audio/x-wav', 'audio/mpeg',
                        'audio/mp4', 'audio/x-m4a', 'audio/aac', 'audio/flac', 'video/webm',
                        'application/octet-stream'}:
            raise HTTPException(415, 'voice_audio_only')
        folder = manager.reserve()
        try:
            received = 0
            async with asyncio.timeout(45):
                with (folder / 'input.audio').open('wb') as output:
                    async for chunk in request.stream():
                        received += len(chunk)
                        if received > MAX_UPLOAD:
                            raise HTTPException(413, 'voice_too_large')
                        output.write(chunk)
            if received == 0:
                raise HTTPException(422, 'voice_invalid_audio')
            return await manager.execute(folder, request)
        except TimeoutError as exc:
            raise HTTPException(408, 'voice_upload_timeout') from exc
        finally:
            manager.release(folder)
