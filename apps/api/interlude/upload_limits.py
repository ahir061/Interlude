"""Bound incoming bytes before multipart parsing spools the complete request."""
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class UploadLimitMiddleware:
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') != 'POST' or scope.get('path') != '/api/videos':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        # Multipart overhead is bounded separately from the file's exact limit.
        limit = self.max_bytes + 1024*1024
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'detail':'invalid_content_length'},status_code=400)(scope,receive,send)
        if length > limit:
            return await JSONResponse({'detail':'upload_limit_exceeded'},status_code=413)(scope,receive,send)
        consumed = 0

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get('body', b''))
            if consumed > limit:
                raise HTTPException(413,'upload_limit_exceeded')
            return message
        await self.app(scope,bounded_receive,send)
