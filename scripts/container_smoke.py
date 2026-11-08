"""Disposable Linux Docker acceptance; no external account credentials or publishing."""
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
POSTGRES = 'postgres:18.6@sha256:e3d24f6906d0760bf4da0dae872415391ededefad23fd471c47dc53b0ddf3c42'


def docker(*args, input=None):
    return subprocess.check_output(['docker', *args], input=input, text=True).strip()


def main():
    suffix = uuid.uuid4().hex[:10]
    network, database, web = [f'pms-{name}-{suffix}' for name in ['net', 'db', 'web']]
    started = []
    docker('network', 'create', '--internal', network)
    try:
        docker('run', '-d', '--name', database, '--network', network,
               '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', POSTGRES)
        started.append(database)
        for _ in range(60):
            if subprocess.run(['docker', 'exec', database, 'pg_isready', '-U', 'postgres'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Disposable database did not become ready')
        # Trust is confined to this disposable internal Docker network, never cloud config.
        schema = (ROOT/'deploy/postgres-schema-proposal.sql').read_text()
        roles = (ROOT/'deploy/database-roles.review.sql').read_text()
        docker('exec', '-i', database, 'psql', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1',
               input='CREATE ROLE pms_writer LOGIN; CREATE ROLE pms_public_read LOGIN;\n'+schema+roles)
        seed = '''from paper_pms.postgres import PostgresStore
p={'reconciled':True,'mode':'synthetic-replay','session_dates':['2026-11-10'],
'research_commit':'container-test-fixture','limitations':['Synthetic container acceptance only'],
'accounts':[], 'private_secret':'must-not-be-public'}
s=PostgresStore('host=DATABASE user=pms_writer dbname=postgres')
try:
 assert s.save('container-fixture',p)[1]
 assert not s.save('container-fixture',p)[1]
finally: s.close()
'''.replace('DATABASE', database)
        docker('run', '--rm', '-i', '--network', network, 'pms-web:test', 'python', '-', input=seed)
        docker('run', '-d', '--name', web, '--network', network, '--read-only',
               '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges', '-p', '127.0.0.1::8080',
               '-e', f'PMS_PUBLIC_DATABASE_URL=host={database} user=pms_public_read dbname=postgres',
               'pms-web:test')
        started.append(web)
        port = docker('port', web, '8080/tcp').rsplit(':', 1)[1]
        base = f'http://127.0.0.1:{port}'
        def request(path, method='GET'):
            try:
                response = urllib.request.urlopen(urllib.request.Request(base+path, method=method), timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            return response.status, response.read(), response.headers
        for _ in range(30):
            try:
                if request('/health/live')[0] == 200:
                    break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Web container did not become ready')
        assert docker('exec', web, 'id', '-u') == '65532'
        assert docker('exec', web, 'python', '-c', 'import pathlib; print(pathlib.Path("/app/work").exists())') == 'False'
        for path, expected in [('/',200),('/snapshot.json',200),('/health/freshness',503),('/missing',404)]:
            status, body, headers = request(path)
            assert status == expected, (path, status, body)
            assert b'must-not-be-public' not in body
            assert headers['X-Content-Type-Options'] == 'nosniff'
        assert b'NOT LIVE' in request('/')[1]
        assert json.loads(request('/snapshot.json')[1])['mode'] == 'synthetic-replay'
        assert request('/', 'POST')[0] == 405
        assert request('/', 'HEAD')[1] == b''
        docker('stop', database)
        assert request('/health/live')[0] == 200
        status, body, _ = request('/snapshot.json')
        assert status == 503 and body == b'{"error":"snapshot unavailable"}'
        print('PASS: non-root read-only container; seeded PostgreSQL; public routes; write rejection; database outage.')
    finally:
        for name in reversed(started):
            subprocess.run(['docker','logs',name], check=False)
            subprocess.run(['docker','rm','-f',name], check=False, stdout=subprocess.DEVNULL)
        subprocess.run(['docker','network','rm',network], check=False, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
