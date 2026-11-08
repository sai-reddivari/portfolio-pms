"""Read-only WSGI application. No automatic DB migrations or public write routes."""
import json
import os
from .public import render


def read_public():
    from .postgres import PostgresStore
    store = PostgresStore(os.environ['PMS_PUBLIC_DATABASE_URL'])
    try:
        return store.read_public()
    finally:
        store.close()


def create_app(reader=read_public):
    def app(environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')
        status, content_type = '200 OK', 'application/json; charset=utf-8'
        if method not in {'GET', 'HEAD'}:
            status, body = '405 Method Not Allowed', b'{"error":"read-only"}'
        elif path == '/health/live':
            body = b'{"service":"paper-pms","alive":true}'
        elif path not in {'/', '/snapshot.json', '/health/freshness'}:
            status, body = '404 Not Found', b'{"error":"not found"}'
        else:
            try:
                public = reader()
                if path == '/health/freshness':
                    # Prospective calendar-aware freshness is not certified yet.
                    # A synthetic fixture can never pass a market-freshness check.
                    status = '503 Service Unavailable'
                    body = b'{"fresh":false,"reason":"synthetic-only; prospective freshness not enabled"}'
                elif path == '/snapshot.json':
                    body = json.dumps(public, allow_nan=False).encode()
                else:
                    content_type = 'text/html; charset=utf-8'
                    body = render(public).encode()
            except Exception:
                # DB errors may contain credentials/hostnames: return no raw detail.
                status, body = '503 Service Unavailable', b'{"error":"snapshot unavailable"}'
        headers = [('Content-Type', content_type), ('Content-Length', str(len(body))),
                   ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                   ('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"),
                   ('Referrer-Policy', 'no-referrer')]
        if status.startswith('405'):
            headers.append(('Allow', 'GET, HEAD'))
        start_response(status, headers)
        return [b'' if method == 'HEAD' else body]
    return app


application = create_app()
