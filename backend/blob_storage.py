"""Private Blob adapter using the wire contract in @vercel/blob 2.8.0.

Python SDK 0.0.8 lacks ifMatch/useCache; keep the small HTTP adapter explicit
and contract-tested. No arbitrary URL or alternate API host is accepted.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path, PurePosixPath
import base64
import hashlib
import hmac
import json
import os
import re
import tempfile
import time
from urllib.parse import quote

import httpx
from backend.repository import WriteConflict

FETCH_DOWNLOAD = ContextVar('fetch_download', default=False)
API = 'https://vercel.com/api/blob'


class BlobFileStore:
    def __init__(self, *, token=None, prefix=None, transport=None):
        self.token = token or os.environ.get('BLOB_READ_WRITE_TOKEN', '')
        self.prefix = prefix or os.environ.get('CONSIGN_BLOB_PREFIX', '')
        parts = self.token.split('_')
        if len(parts) < 5 or parts[:3] != ['vercel', 'blob', 'rw'] or not re.fullmatch(r'[A-Za-z0-9]+', parts[3]):
            raise ValueError('Configure a Blob read-write token in server environment')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', self.prefix):
            raise ValueError('CONSIGN_BLOB_PREFIX must be an explicit environment namespace')
        self.store_id = parts[3].lower()
        self.transport = transport

    def key(self, key):
        parts = PurePosixPath(key)
        if not key or parts.is_absolute() or '..' in parts.parts or '\\' in key or '//' in key:
            raise ValueError('Invalid storage key')
        return self.prefix+'/'+key

    def request(self, method, url, **kwargs):
        max_bytes = kwargs.pop('max_bytes', 260 * 1024 * 1024)
        headers = {'Authorization': 'Bearer '+self.token, 'x-api-version': '12'}
        headers.update(kwargs.pop('headers', {}))
        try:
            with httpx.Client(transport=self.transport, timeout=60, follow_redirects=False) as client:
                with client.stream(method, url, headers=headers, **kwargs) as streamed:
                    chunks=[]; total=0
                    for chunk in streamed.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes: raise OSError('Blob exceeds configured size limit')
                        chunks.append(chunk)
                    # iter_bytes() already decodes HTTP content encodings. Preserve
                    # ETag for conditional writes, but discard encoded-body headers.
                    decoded_headers = httpx.Headers(streamed.headers)
                    for name in ('content-encoding', 'content-length', 'transfer-encoding'):
                        decoded_headers.pop(name, None)
                    response=httpx.Response(streamed.status_code,headers=decoded_headers,content=b''.join(chunks))
        except httpx.TransportError:
            raise OSError('Blob service connection failed') from None
        if response.status_code in (409, 412): raise WriteConflict('Blob version conflict')
        if response.status_code == 404: return response
        if not response.is_success:
            try: code=response.json().get('error', {}).get('code')
            except ValueError: code=None
            if code == 'precondition_failed': raise WriteConflict('Blob version conflict')
            raise OSError(f'Blob operation failed (HTTP {response.status_code})')
        return response

    def read_version(self, key):
        path = self.key(key)
        response = self.request('GET', f'https://{self.store_id}.private.blob.vercel-storage.com/{quote(path, safe="/")}', params={'cache': '0'}, max_bytes=64*1024*1024 if key == 'state/system.json' else 260*1024*1024)
        if response.status_code == 404: return None, None
        etag = response.headers.get('etag')
        if not etag: raise OSError('Blob response missing ETag; refusing unsafe writes')
        return response.content, etag

    def read(self, key):
        content, _ = self.read_version(key)
        if content is None: raise FileNotFoundError(key)
        return content

    def exists(self, key):
        response = self.request('GET', API, params={'url': self.key(key)})
        return response.status_code != 404

    def put(self, key, content, expected=None):
        headers={'x-vercel-blob-access':'private', 'x-add-random-suffix':'0',
                 'x-allow-overwrite':'1' if expected is not None else '0',
                 'x-content-type':'application/json' if key.endswith('.json') else 'application/octet-stream'}
        if expected is not None: headers['x-if-match'] = expected
        response = self.request('PUT', API, params={'pathname': self.key(key)}, content=content, headers=headers)
        if response.status_code == 404: raise OSError('Blob store not found')

    def compare_and_swap(self, key, content, expected): self.put(key, content, expected)
    def write(self, key, content): self.put(key, content)

    def delete(self, key):
        self.request('POST', API+'/delete', json={'urls': [self.key(key)]})

    def list(self, prefix=''):
        params={'prefix':self.prefix+'/'+prefix.rstrip('/')+'/', 'limit':1000}
        rows=[]
        while True:
            response=self.request('GET', API, params=params)
            if response.status_code == 404: raise OSError('Blob store not found')
            result=response.json()
            for item in result['blobs']:
                if item['pathname'].startswith(self.prefix+'/'):
                    rows.append(dict(key=item['pathname'][len(self.prefix)+1:],bytes=item['size']))
            if not result.get('hasMore'): break
            if not result.get('cursor'): raise OSError('Blob listing missing cursor')
            params['cursor']=result['cursor']
        return sorted(rows,key=lambda row:row['key'])

    def prepare(self): pass

    @contextmanager
    def materialize(self, key):
        with tempfile.TemporaryDirectory(prefix='consign-blob-') as folder:
            path=Path(folder)/('asset'+PurePosixPath(key).suffix)
            path.write_bytes(self.read(key))
            yield path

    def write_from(self, key, producer):
        with tempfile.TemporaryDirectory(prefix='consign-export-') as folder:
            path=Path(folder)/('export'+PurePosixPath(key).suffix)
            producer(path)
            self.write(key, path.read_bytes())

    def response(self, key, filename, **kwargs):
        from starlette.responses import JSONResponse, RedirectResponse
        body=json.dumps({'key':self.key(key),'filename':filename,'expires':int(time.time())+300},separators=(',',':')).encode()
        encoded=base64.urlsafe_b64encode(body).decode().rstrip('=')
        signature=hmac.new(self.token.encode(),encoded.encode(),hashlib.sha256).hexdigest()
        location='/cloud-download?ticket='+encoded+'.'+signature
        headers=kwargs.get('headers', {}) | {'Cache-Control':'no-store'}
        if FETCH_DOWNLOAD.get():
            return JSONResponse({'download':location},headers=headers | {'X-Consign-Download':'1'})
        return RedirectResponse(location,status_code=303,headers=headers)
