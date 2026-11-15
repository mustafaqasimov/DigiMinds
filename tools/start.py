"""Local one-click setup and verified browser launch; standard library only.

Windows: double-click BASLAT.cmd. Other systems: python tools/start.py.
Only the base application dependencies are installed; vision stays optional.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
# Local readiness traffic must stay on loopback, including with a system proxy.
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def healthy(url):
    try:
        with HTTP.open(url + '/api/health', timeout=.5) as response:
            body = json.loads(response.read(4096))
            return body.get('ok') is True and body.get('dataset') == 'synthetic-training-baku-v1'
    except (OSError, ValueError, urllib.error.URLError):
        return False


def choose_port(preferred):
    for port in range(preferred, min(preferred + 11, 65536)):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError('3000-3010 portlari mesguldur. --port ile basqa port secin.')


def prepare_python():
    env_dir = ROOT / '.venv'
    executable = env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not executable.is_file():
        print('[1/3] Python muhiti yaradilir...', flush=True)
        subprocess.run([sys.executable, '-m', 'venv', str(env_dir)], check=True, cwd=ROOT)
    requirements = ROOT / 'requirements.txt'
    stamp = env_dir / '.digiminds-requirements.sha256'
    signature = hashlib.sha256(requirements.read_bytes()).hexdigest()
    matches = stamp.is_file() and stamp.read_text().strip() == signature
    imports_work = subprocess.run(
        [str(executable), '-c', 'import fastapi, uvicorn, httpx, pydantic'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
    if not matches or not imports_work:
        print('[2/3] Lazimi paketler qurasdirilir. Ilk defe internet lazimdir...', flush=True)
        subprocess.run([str(executable), '-m', 'pip', 'install', '-r', str(requirements)],
                       check=True, cwd=ROOT)
        stamp.write_text(signature)
    else:
        print('[2/3] Paketler hazirdir; yeniden endirilmir.', flush=True)
    return executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=3000)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--smoke-test', action='store_true', help='Verify HTTP startup, then stop; no browser')
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise RuntimeError('Python 3.12 ve ya daha yeni versiya lazimdir.')
    if not 1024 <= args.port <= 65535:
        parser.error('Port 1024..65535 araliginda olmalidir')

    default_url = f'http://127.0.0.1:{args.port}'
    if not args.smoke_test and healthy(default_url):
        print(f'DigiMinds artiq isleyir: {default_url}', flush=True)
        if not args.no_browser:
            webbrowser.open(default_url)
        return 0

    executable = prepare_python()
    port = choose_port(args.port)
    url = f'http://127.0.0.1:{port}'
    print(f'[3/3] Server basladilir: {url}', flush=True)
    process = subprocess.Popen([str(executable), str(ROOT / 'tools/dev.py'),
                                '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT)
    try:
        deadline = time.monotonic() + 30
        while not healthy(url):
            if process.poll() is not None:
                raise RuntimeError('Server baslamadi. Yuxaridaki xeta metnine baxin.')
            if time.monotonic() >= deadline:
                raise RuntimeError('Server 30 saniye erzinde cavab vermedi.')
            time.sleep(.2)
        with HTTP.open(url, timeout=3) as response:
            if response.status != 200 or b'DigiMinds' not in response.read():
                raise RuntimeError('Panelin sehifesi acilmadi.')
        print(f'HAZIR: {url}', flush=True)
        if args.smoke_test:
            print('HTTP readiness and frontend document: PASS', flush=True)
            return 0
        if not args.no_browser:
            webbrowser.open(url)
        print('Bu pencereni aciq saxlayin. Dayandirmaq: Ctrl+C.', flush=True)
        return process.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f'XETA: {error}', file=sys.stderr)
        raise SystemExit(1)
