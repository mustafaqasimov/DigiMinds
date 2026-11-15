"""Bounded, owner-scoped video jobs for the single-process local prototype."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

MAX_UPLOAD = 100 * 1024 * 1024
MAX_SECONDS = 60
JOB_TIMEOUT = 600
RETENTION = 3600
TERMINAL = {'completed', 'failed', 'cancelled'}


def available():
    return all(importlib.util.find_spec(name) is not None
               for name in ('ultralytics', 'cv2', 'imageio_ffmpeg'))


def terminate_tree(process):
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is None:
            process.kill()


class VisionJobs:
    def __init__(self, root, directory):
        self.root = Path(root)
        self.directory = Path(directory)
        self.lock = threading.RLock()
        self.jobs = {}
        self.active = None
        self.closed = False
        self.thread = None
        self.process = None
        # Job ownership is intentionally transient. A restart removes old media.
        if self.directory.exists():
            for path in self.directory.iterdir():
                if path.is_dir() and re.fullmatch(r'[a-f0-9]{32}', path.name):
                    shutil.rmtree(path, ignore_errors=True)

    def prune(self):
        with self.lock:
            now = time.time()
            removable = sorted((j for j in self.jobs.values() if j['state'] in TERMINAL and j['id'] != self.active),
                                key=lambda j: j['created_at'])
            for job in removable:
                if now-job['created_at'] > RETENTION or len(self.jobs) >= 8:
                    shutil.rmtree(self.directory/job['id'], ignore_errors=True)
                    self.jobs.pop(job['id'], None)

    def reserve(self, owner, filename):
        with self.lock:
            self.prune()
            if self.active or self.closed:
                raise HTTPException(409, 'vision_busy')
            job_id = uuid4().hex
            folder = self.directory/job_id
            folder.mkdir(parents=True, mode=0o700)
            job = {'id': job_id, 'owner': owner, 'filename': filename, 'state': 'uploading',
                   'created_at': time.time(), 'progress': 0, 'frames_processed': 0,
                   'total_frames': 0, 'count': None, 'error': None}
            self.jobs[job_id] = job
            self.active = job_id
            return job_id, folder

    def own(self, job_id, owner):
        job = self.jobs.get(job_id)
        if not job or job['owner'] != owner or time.time()-job['created_at'] > RETENTION:
            raise HTTPException(404, 'vision_not_found')
        return job

    def snapshot(self, job_id, owner):
        with self.lock:
            job = self.own(job_id, owner)
            return {k: v for k, v in job.items() if k != 'owner'}

    def discard_upload(self, job_id):
        with self.lock:
            shutil.rmtree(self.directory/job_id, ignore_errors=True)
            self.jobs.pop(job_id, None)
            if self.active == job_id:
                self.active = None

    def start(self, job_id):
        with self.lock:
            if self.closed:
                raise RuntimeError('Server is shutting down')
            self.jobs[job_id]['state'] = 'queued'
            self.thread = threading.Thread(target=self.execute, args=(job_id,), daemon=True)
            self.thread.start()

    def read_progress(self, job_id):
        try:
            progress = json.loads((self.directory/job_id/'status.json').read_text())
        except (OSError, ValueError):
            return
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job['state'] not in TERMINAL:
                job.update(progress)

    def execute(self, job_id):
        folder = self.directory/job_id
        process = None
        try:
            with (folder/'worker.log').open('wb') as log:
                with self.lock:
                    if self.jobs[job_id]['state'] == 'cancelled' or self.closed:
                        return
                    process = subprocess.Popen(
                        [sys.executable, '-m', 'vision.web_job', str(folder)], cwd=self.root,
                        stdout=log, stderr=log, start_new_session=os.name != 'nt',
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
                    self.process = process
                deadline = time.monotonic() + JOB_TIMEOUT
                while process.poll() is None:
                    self.read_progress(job_id)
                    with self.lock:
                        cancelled = self.jobs[job_id]['state'] == 'cancelled' or self.closed
                    if cancelled or time.monotonic() > deadline:
                        terminate_tree(process)
                        if not cancelled:
                            with self.lock:
                                self.jobs[job_id].update(state='failed', error='vision_timeout')
                        break
                    time.sleep(.2)
                self.read_progress(job_id)
                with self.lock:
                    job = self.jobs[job_id]
                    if job['state'] not in TERMINAL:
                        job.update(state='failed', error='vision_failed')
                    elif job['state'] == 'completed' and (process.returncode != 0 or
                            not (folder/'result.mp4').is_file() or not (folder/'report.json').is_file()):
                        job.update(state='failed', error='vision_failed')
        except Exception:
            terminate_tree(process)
            with self.lock:
                if job_id in self.jobs and self.jobs[job_id]['state'] != 'cancelled':
                    self.jobs[job_id].update(state='failed', error='vision_failed')
        finally:
            with self.lock:
                job = self.jobs.get(job_id)
                if job and job['state'] in {'failed', 'cancelled'}:
                    shutil.rmtree(folder, ignore_errors=True)
                else:
                    (folder/'input.video').unlink(missing_ok=True)
                self.process = None
                if self.active == job_id:
                    self.active = None

    def cancel(self, job_id, owner):
        with self.lock:
            job = self.own(job_id, owner)
            if job['state'] not in TERMINAL:
                job.update(state='cancelled', error=None)
            return {k: v for k, v in job.items() if k != 'owner'}

    def close(self):
        with self.lock:
            self.closed = True
            process = self.process
        terminate_tree(process)
        if self.thread:
            self.thread.join(timeout=12)


def install_vision(app, manager, require, throttle, demo):
    @app.get('/api/vision/status')
    def status():
        manager.prune()
        return {'available': available(), 'demo': demo, 'model': 'YOLO26n',
                'max_upload_bytes': MAX_UPLOAD, 'max_seconds': MAX_SECONDS,
                'max_width': 1920, 'max_height': 1920, 'max_pixels': 1920*1080,
                'retention_seconds': RETENTION}

    @app.post('/api/vision/jobs', status_code=202)
    async def upload(request: Request, filename: str = 'video.mp4'):
        user = require(request, 'dashboard:read')
        throttle('vision-upload:'+user['id'], 12, 3600)
        if not available():
            raise HTTPException(503, 'vision_not_installed')
        if len(filename) > 160 or '/' in filename or '\\' in filename or any(ord(c)<32 for c in filename):
            raise HTTPException(422, 'vision_invalid_filename')
        if Path(filename).suffix.lower() not in {'.mp4', '.mov', '.webm', '.avi'}:
            raise HTTPException(415, 'vision_video_only')
        job_id, folder = manager.reserve(user['id'], filename)
        received = 0
        try:
            async with asyncio.timeout(90):
                with (folder/'input.video').open('wb') as output:
                    async for chunk in request.stream():
                        received += len(chunk)
                        if received > MAX_UPLOAD:
                            raise HTTPException(413, 'vision_upload_too_large')
                        output.write(chunk)
            if received == 0:
                raise HTTPException(422, 'vision_empty_video')
            manager.start(job_id)
        except BaseException as exc:
            manager.discard_upload(job_id)
            if isinstance(exc, TimeoutError):
                raise HTTPException(408, 'vision_upload_timeout') from exc
            raise
        return manager.snapshot(job_id, user['id'])

    @app.get('/api/vision/jobs/{job_id}')
    def get_job(job_id: str, request: Request):
        user = require(request, 'dashboard:read')
        return manager.snapshot(job_id, user['id'])

    @app.delete('/api/vision/jobs/{job_id}')
    def cancel_job(job_id: str, request: Request):
        user = require(request, 'dashboard:read')
        return manager.cancel(job_id, user['id'])

    @app.get('/api/vision/jobs/{job_id}/{asset}')
    def get_asset(job_id: str, asset: str, request: Request, download: bool = False):
        user = require(request, 'dashboard:read')
        job = manager.snapshot(job_id, user['id'])
        assets = {'preview': ('preview.jpg', 'image/jpeg'),
                  'video': ('result.mp4', 'video/mp4'),
                  'report': ('report.json', 'application/json')}
        if asset not in assets or (asset != 'preview' and job['state'] != 'completed'):
            raise HTTPException(404, 'vision_result_not_ready')
        filename, mime = assets[asset]
        path = manager.directory/job_id/filename
        if not path.is_file():
            raise HTTPException(404, 'vision_result_not_ready')
        return FileResponse(path, media_type=mime,
                            filename=('DigiMinds-YOLO26'+path.suffix) if download else None)
