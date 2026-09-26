"""Signed, expiring HttpOnly sessions for one protected team workspace."""
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

COOKIE = "interlude_session"


class Login(BaseModel):
    password: str = Field(max_length=512)


def install_auth(app, settings):
    password = settings.workspace_password.get_secret_value()
    secret = settings.session_secret.get_secret_value().encode()
    attempts = defaultdict(deque)

    def signature(payload):
        return hmac.new(secret,payload.encode(),hashlib.sha256).hexdigest()

    def valid(token):
        try:
            payload,sig=token.rsplit('.',1)
            expires,_=payload.split(':',1)
            return int(expires)>time.time() and hmac.compare_digest(sig,signature(payload))
        except (ValueError,AttributeError):
            return False

    @app.middleware("http")
    async def protect(request,call_next):
        public = request.url.path in ('/api/session','/api/config') or not request.url.path.startswith('/api/')
        if password and not public and request.method != 'OPTIONS':
            if not valid(request.cookies.get(COOKIE,'')):
                return JSONResponse({'detail':'authentication_required'},status_code=401)
            if request.method not in ('GET','HEAD') and request.headers.get('x-interlude-request')!='1':
                return JSONResponse({'detail':'csrf_header_required'},status_code=403)
        return await call_next(request)

    @app.get('/api/session')
    def session(request:Request):
        return {'authenticated':not password or valid(request.cookies.get(COOKIE,'')), 'protected':bool(password)}

    @app.post('/api/session')
    def login(body:Login,request:Request):
        origin=request.headers.get('origin')
        if origin and origin not in settings.cors_origins and origin != str(request.base_url).rstrip('/'):
            raise HTTPException(403,'origin_not_allowed')
        key=request.client.host if request.client else 'unknown'
        now=time.time()
        # Bound memory as well as attempts. Proxy deployments additionally limit requests.
        if len(attempts)>10000:
            attempts.clear()
        queue=attempts[key]
        while queue and queue[0]<now-60:
            queue.popleft()
        if len(queue)>=10:
            raise HTTPException(429,'login_rate_limited')
        queue.append(now)
        if password and not hmac.compare_digest(body.password.encode(),password.encode()):
            raise HTTPException(401,'invalid_password')
        payload=f'{int(now)+settings.session_ttl_sec}:{secrets.token_hex(16)}'
        response=JSONResponse({'authenticated':True,'protected':bool(password)})
        response.set_cookie(COOKIE,payload+'.'+signature(payload),max_age=settings.session_ttl_sec,
                            httponly=True,secure=settings.session_cookie_secure,samesite='strict',path='/')
        return response

    @app.post('/api/session/logout')
    def logout():
        response=JSONResponse({'authenticated':False})
        response.delete_cookie(COOKIE,path='/')
        return response
