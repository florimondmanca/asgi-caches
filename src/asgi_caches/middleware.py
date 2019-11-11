import typing

from caches import Cache
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .exceptions import RequestNotCachable, ResponseNotCachable
from .utils import get_from_cache, store_in_cache


class CacheMiddleware:
    def __init__(self, app: ASGIApp, *, cache: Cache) -> None:
        self.app = app
        self.cache = cache

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        responder = CacheResponder(self.app, cache=self.cache)
        await responder(scope, receive, send)


class CacheResponder:
    def __init__(self, app: ASGIApp, *, cache: Cache) -> None:
        self.app = app
        self.cache = cache
        self.send: Send = unattached_send
        self.initial_message: Message = {}
        self.is_response_cachable = True
        self.request: typing.Optional[Request] = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"

        request = Request(scope)

        try:
            response = await get_from_cache(request, cache=self.cache)
        except RequestNotCachable:
            await self.app(scope, receive, send)
        else:
            if response is not None:
                await response(scope, receive, send)
                return
            self.request = request
            self.send = send
            await self.app(scope, receive, self.send_with_caching)

    async def send_with_caching(self, message: Message) -> None:
        if not self.is_response_cachable:
            await self.send(message)
            return

        if message["type"] == "http.response.start":
            # Defer sending this message until we figured out
            # whether the response can be cached.
            self.initial_message = message
            return

        assert message["type"] == "http.response.body"
        if message.get("more_body", False):
            # Streaming response.
            self.is_response_cachable = False
            await self.send(self.initial_message)
            await self.send(message)
            return

        assert self.request is not None
        body = message["body"]
        response = Response(content=body, status_code=self.initial_message["status"])
        # NOTE: be sure not to mutate the original headers directly, as another Response
        # object might be holding a reference to the same list.
        response.raw_headers = list(self.initial_message["headers"])

        try:
            await store_in_cache(response, request=self.request, cache=self.cache)
        except ResponseNotCachable:
            self.is_response_cachable = False
        else:
            # Apply any headers added or modified by 'store_in_cache()'.
            self.initial_message["headers"] = list(response.raw_headers)

        await self.send(self.initial_message)
        await self.send(message)


async def unattached_receive() -> Message:
    raise RuntimeError("receive awaitable not set")  # pragma: no cover


async def unattached_send(message: Message) -> None:
    raise RuntimeError("send awaitable not set")  # pragma: no cover
