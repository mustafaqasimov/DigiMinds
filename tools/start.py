"""Local one-click setup and verified browser launch; standard library only.

Windows: double-click BASLAT.cmd. Other systems: python tools/start.py.
Only the base application dependencies are installed; vision stays optional.
"""
import argparse
import hashlib
import json
import ipaddress
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
# Local readiness traffic must stay on loopback, including with a system proxy.
# The LAN certificate is self-signed, so the loopback readiness probe skips verification.
_LOCAL_TLS = ssl.create_default_context()
_LOCAL_TLS.check_hostname = False
_LOCAL_TLS.verify_mode = ssl.CERT_NONE
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=_LOCAL_TLS))


def healthy(url):
    try:
        with HTTP.open(url + '/api/health', timeout=.5) as response:
            body = json.loads(response.read(4096))
            return body.get('ok') is True and body.get('dataset') == 'synthetic-training-baku-v1'
    except (OSError, ValueError, urllib.error.URLError):
        return False


def choose_port(preferred, host='127.0.0.1'):
    for port in range(preferred, min(preferred + 11, 65536)):
        with socket.socket() as probe:
            try:
                probe.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError('3000-3010 portlari mesguldur. --port ile basqa port secin.')


def lan_address():
    """Private Wi-Fi/LAN address; UDP connect selects a route without sending a packet."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1', 9))
            address = probe.getsockname()[0]
        ip = ipaddress.ip_address(address)
        if ip.is_private and not ip.is_loopback and not ip.is_link_local:
            return address
    except OSError:
        pass
    return None


def find_openssl():
    found = shutil.which('openssl')
    if found:
        return found
    for base in (os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', '')):
        for sub in ('Git/usr/bin/openssl.exe', 'Git/mingw64/bin/openssl.exe'):
            if base and (Path(base) / sub).is_file():
                return str(Path(base) / sub)
    raise RuntimeError('openssl tapilmadi. Git for Windows qurasdirin ve ya openssl-i PATH-e elave edin.')


def certificate(ip):
    """Self-signed certificate for this LAN address. Phones expose motion sensors only over HTTPS."""
    folder = ROOT / 'data/tls'
    cert, key, stamp = folder / 'cert.pem', folder / 'key.pem', folder / 'address.txt'
    if cert.is_file() and key.is_file() and stamp.is_file() and stamp.read_text().strip() == ip:
        return cert, key
    folder.mkdir(parents=True, exist_ok=True)
    print('[TLS] Sertifikat yaradilir:', ip, flush=True)
    subprocess.run([find_openssl(), 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '30',
                    '-keyout', str(key), '-out', str(cert), '-subj', '/CN=DigiMinds LAN demo',
                    '-addext', f'subjectAltName=IP:{ip},IP:127.0.0.1,DNS:localhost'],
                   check=True, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stamp.write_text(ip)
    return cert, key


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
    parser.add_argument('--lan', action='store_true', help='Allow devices on your local network to connect')
    parser.add_argument('--jury', action='store_true', help='Open the jury presentation screen')
    parser.add_argument('--https', action='store_true', help='LAN + HTTPS with a self-signed certificate, for phone motion sensors')
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise RuntimeError('Python 3.12 ve ya daha yeni versiya lazimdir.')
    if not 1024 <= args.port <= 65535:
        parser.error('Port 1024..65535 araliginda olmalidir')

    if args.https:
        args.lan = True
    scheme = 'https' if args.https else 'http'
    default_url = f'{scheme}://127.0.0.1:{args.port}'
    entry='/presentation.html' if args.jury else '/'
    if not args.smoke_test and not args.lan and healthy(default_url):
        print(f'DigiMinds artiq isleyir: {default_url}', flush=True)
        if not args.no_browser:
            webbrowser.open(default_url+entry)
        return 0

    executable = prepare_python()
    host='0.0.0.0' if args.lan else '127.0.0.1'
    port = choose_port(args.port,host)
    url = f'{scheme}://127.0.0.1:{port}'
    command = [str(executable), str(ROOT / 'tools/dev.py'), '--host', host, '--port', str(port)]
    env = None
    if args.https:
        ip = lan_address()
        if not ip:
            raise RuntimeError('Wi-Fi/LAN IPv4 unvani tapilmadi. Noutbuku Wi-Fi ve ya hotspot-a qosun.')
        cert, key = certificate(ip)
        command += ['--ssl-certfile', str(cert), '--ssl-keyfile', str(key)]
        env = {**os.environ, 'DIGIMINDS_PUBLIC_URL': f'https://{ip}:{port}'}
    print(f'[3/3] Server basladilir: {url}', flush=True)
    process = subprocess.Popen(command, cwd=ROOT, env=env)
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
        if args.lan:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                    probe.connect(('192.0.2.1',9))
                    addresses=[probe.getsockname()[0]]
                for address in addresses:
                    ip=ipaddress.ip_address(address)
                    if ip.is_private and not ip.is_loopback and not ip.is_link_local:
                        print(f'TELEFON PULTU: {scheme}://{address}:{port}/remote.html?room=DIGI26', flush=True)
            except OSError:
                print('Wi-Fi IPv4 unvanini ipconfig ile tapin.', flush=True)
            if args.https:
                print(f'SENSOR SEHIFESI (telefonlar): https://{ip}:{port}/sensor', flush=True)
                print('Brauzer xeberdarliq versə: Advanced / Etrafli -> Proceed / Davam et.', flush=True)
            print('Telefon ve noutbuk eyni Wi-Fi/hotspot-da olmalidir.', flush=True)
        if args.smoke_test:
            print('HTTP readiness and frontend document: PASS', flush=True)
            return 0
        if not args.no_browser:
            webbrowser.open(url+entry)
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
