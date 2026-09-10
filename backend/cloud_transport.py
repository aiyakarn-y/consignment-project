"""Rehydrate an authenticated staged multipart request without a Function upload.

Only server-issued staging paths in this environment are accepted. Ordinary
local requests keep their existing multipart behavior.
"""
import re
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from backend.blob_storage import FETCH_DOWNLOAD


class CloudTransportMiddleware:
    def __init__(self, app): self.app=app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http': return await self.app(scope,receive,send)
        from backend import app as service
        headers=dict(scope['headers'])
        token=FETCH_DOWNLOAD.set(headers.get(b'x-consign-fetch') == b'1')
        key=None
        try:
            staged=headers.get(b'x-consign-upload')
            if staged:
                path=scope['path']
                allowed=re.fullmatch(r'/api/(?:profiles/(?:inspect|preview)|backups/(?:preview|restore)|batches/[0-9a-f]{32}/(?:check-upload|upload|master))',path)
                if service.STORAGE_DRIVER != 'vercel_blob' or scope['method'] != 'POST' or not allowed or not re.fullmatch(rb'staging/[0-9a-f]{32}',staged):
                    return await JSONResponse({'detail':'Invalid staged upload'},status_code=400)(scope,receive,send)
                if not headers.get(b'content-type',b'').startswith(b'multipart/form-data;'):
                    return await JSONResponse({'detail':'Expected multipart upload'},status_code=400)(scope,receive,send)
                key=staged.decode()
                content=await run_in_threadpool(service.storage().read,key)
                if len(content)>260*1024*1024:
                    return await JSONResponse({'detail':'Upload exceeds 260 MiB'},status_code=413)(scope,receive,send)
                scope=dict(scope,headers=[(k,v) for k,v in scope['headers'] if k not in (b'content-length',b'x-consign-upload')]+[(b'content-length',str(len(content)).encode())])
                original_receive=receive
                sent=False
                async def staged_receive():
                    nonlocal sent
                    if not sent:
                        sent=True
                        return {'type':'http.request','body':content,'more_body':False}
                    return await original_receive()
                receive=staged_receive
            await self.app(scope,receive,send)
        except FileNotFoundError:
            await JSONResponse({'detail':'ไฟล์อัปโหลดหมดอายุ กรุณาเลือกไฟล์อีกครั้ง'},status_code=410)(scope,receive,send)
        finally:
            FETCH_DOWNLOAD.reset(token)
            if key:
                try: await run_in_threadpool(service.storage().delete,key)
                except OSError: pass
