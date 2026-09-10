"""Shared beta credentials; application users are not separate accounts."""
import base64
import binascii
import hmac
import os

from starlette.responses import JSONResponse


def install_beta_auth(app):
    @app.middleware('http')
    async def beta_auth(request, call_next):
        mode = os.environ.get('CONSIGN_BETA_MODE')
        on_vercel = os.environ.get('VERCEL') == '1'
        if mode == '0' or (mode != '1' and not on_vercel):
            response = await call_next(request)
            if on_vercel:
                response.headers['Cache-Control'] = 'no-store'
            return response
        password = os.environ.get('CONSIGN_BETA_PASSWORD', '')
        username = os.environ.get('CONSIGN_BETA_USER', 'beta')
        if not password:
            return JSONResponse({'detail': 'Beta credentials are not configured'}, status_code=503)
        try:
            scheme, value = request.headers.get('authorization', '').split(' ', 1)
            supplied = base64.b64decode(value, validate=True)
            valid = scheme.lower() == 'basic' and hmac.compare_digest(supplied, f'{username}:{password}'.encode())
        except (ValueError, binascii.Error):
            valid = False
        if not valid:
            return JSONResponse({'detail': 'Beta login required'}, status_code=401,
                                headers={'WWW-Authenticate': 'Basic realm="ConsignmentSystem Beta", charset="UTF-8"', 'Cache-Control': 'no-store'})
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response
