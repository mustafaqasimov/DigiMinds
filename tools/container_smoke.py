"""Verify demo HTTP startup and persisted SOS/JWT state across container recreation.

Standard library only. Creates one synthetic SOS; use a disposable demo deployment.
The private state file contains a temporary demo token and must not be published.
"""
import argparse
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['seed', 'verify'])
    parser.add_argument('--base-url', default='http://127.0.0.1:3000')
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, body=None, token=None, expected=200, decode_json=False):
        headers = {'X-Requested-With': 'DigiMinds'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if body is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(args.base_url.rstrip('/') + path,
            data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            response = opener.open(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            payload = response.read()
            assert response.status == expected, (path, response.status, expected)
            content_type = response.headers.get('Content-Type', '')
        mime = content_type.split(';', 1)[0].strip()
        return json.loads(payload) if decode_json or mime == 'application/json' or mime.endswith('+json') else payload

    health = request('/api/health')
    assert health['ok'] and health['demo'], 'Smoke test requires a disposable demo server'
    assert b'DigiMinds' in request('/workspace.html')
    assert len(request('/app.js')) > 100
    # Slim images may lack the OS MIME mapping for .geojson; verify its content.
    assert request('/baku.geojson', decode_json=True)['type'] == 'FeatureCollection'
    request('/api/state', expected=401)
    if args.phase == 'seed':
        token = request('/api/auth/guest', {})['token']
        assert len(token.split('.')) == 3
        payload = {'event_key': str(uuid.uuid4()), 'type': 'medical',
                   'lat': 40.37, 'lng': 49.8385}
        created = request('/api/sos', payload, token, expected=201)
        assert created['created'] is True
        state = {'token': token, 'payload': payload, 'report_id': created['report']['id']}
        with open(args.state, 'w', opener=lambda p, flags: os.open(p, flags, 0o600)) as output:
            json.dump(state, output)
    else:
        state = json.loads(args.state.read_text())
    repeated = request('/api/sos', state['payload'], state['token'])
    assert repeated['created'] is False
    assert repeated['report']['id'] == state['report_id']
    request('/api/auth/me', token=state['token'])
    if args.phase == 'verify':
        args.state.unlink()
    print('PASS:', args.phase, 'HTTP assets, JWT auth, SOS persistence and deduplication')


if __name__ == '__main__':
    main()
