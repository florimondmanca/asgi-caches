import datetime as dt
import gzip
import typing

import httpx
import pytest
from caches import Cache
from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from asgi_caches.middleware import CacheMiddleware
from tests.utils import ComparableHTTPXResponse, mock_receive, mock_send


class CacheSpy:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.misses = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.misses += 1
        await self.app(scope, receive, send)


@pytest.mark.asyncio
async def test_cache_response() -> None:
    cache = Cache("locmem://null", ttl=2 * 60)
    spy = CacheSpy(PlainTextResponse("Hello, world!"))
    app = CacheMiddleware(spy, cache=cache)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        assert spy.misses == 0

        r = await client.get("/")
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert spy.misses == 1

        assert "Expires" in r.headers
        expires_fmt = "%a, %d %b %Y %H:%M:%S GMT"
        expires = dt.datetime.strptime(r.headers["Expires"], expires_fmt)
        delta: dt.timedelta = expires - dt.datetime.utcnow()
        assert delta.total_seconds() == pytest.approx(120, abs=1)
        assert "Cache-Control" in r.headers
        assert r.headers["Cache-Control"] == "max-age=120"

        r1 = await client.get("/")
        assert spy.misses == 1
        assert ComparableHTTPXResponse(r1) == r

        r2 = await client.get("/")
        assert spy.misses == 1
        assert ComparableHTTPXResponse(r2) == r


@pytest.mark.asyncio
async def test_not_http() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "lifespan"

    cache = Cache("locmem://null")
    app = CacheMiddleware(app, cache=cache)
    await app({"type": "lifespan"}, mock_receive, mock_send)


@pytest.mark.asyncio
async def test_non_cachable_request() -> None:
    cache = Cache("locmem://null")
    spy = CacheSpy(PlainTextResponse("Hello, world!"))
    app = CacheMiddleware(spy, cache=cache)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        assert spy.misses == 0

        r = await client.post("/")
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert "Expires" not in r.headers
        assert "Cache-Control" not in r.headers
        assert spy.misses == 1

        r1 = await client.post("/")
        assert ComparableHTTPXResponse(r1) == r
        assert spy.misses == 2


@pytest.mark.asyncio
async def test_use_cached_head_response_on_get() -> None:
    """
    Making a HEAD request should use the cached response for future GET requests.
    """
    cache = Cache("locmem://null")
    spy = CacheSpy(PlainTextResponse("Hello, world!"))
    app = CacheMiddleware(spy, cache=cache)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        assert spy.misses == 0

        r = await client.head("/")
        assert not r.text
        assert r.status_code == 200
        assert "Expires" in r.headers
        assert "Cache-Control" in r.headers
        assert spy.misses == 1

        r1 = await client.get("/")
        assert r1.text == "Hello, world!"
        assert r1.status_code == 200
        assert "Expires" in r.headers
        assert "Cache-Control" in r.headers
        assert spy.misses == 1


@pytest.mark.parametrize(
    "status_code", (201, 202, 204, 301, 307, 308, 400, 401, 403, 500, 502, 503)
)
@pytest.mark.asyncio
async def test_not_200_ok(status_code: int) -> None:
    """Responses that don't have status code 200 should not be cached."""
    cache = Cache("locmem://null")
    spy = CacheSpy(PlainTextResponse("Hello, world!", status_code=status_code))
    app = CacheMiddleware(spy, cache=cache)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        r = await client.get("/")
        assert r.status_code == status_code
        assert r.text == "Hello, world!"
        assert "Expires" not in r.headers
        assert "Cache-Control" not in r.headers
        assert spy.misses == 1

        r1 = await client.get("/")
        assert ComparableHTTPXResponse(r1) == r
        assert spy.misses == 2


@pytest.mark.asyncio
async def test_streaming_response() -> None:
    """Streaming responses should not be cached."""
    cache = Cache("locmem://null")

    async def body() -> typing.AsyncIterator[str]:
        yield "Hello, "
        yield "world!"

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        response = StreamingResponse(body())
        await response(scope, receive, send)

    spy = CacheSpy(app)
    app = CacheMiddleware(spy, cache=cache)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        assert spy.misses == 0

        r = await client.get("/")
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert spy.misses == 1

        r = await client.get("/")
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert spy.misses == 2


@pytest.mark.asyncio
async def test_vary() -> None:
    """
    Sending different values for request headers registered as varying should
    result in different cache entries.
    """
    cache = Cache("locmem://null")

    async def gzippable_app(scope: Scope, receive: Receive, send: Send) -> None:
        headers = Headers(scope=scope)

        if "gzip" in headers.getlist("accept-encoding"):
            body = gzip.compress(b"Hello, world!")
            response = PlainTextResponse(
                content=body,
                headers={"Content-Encoding": "gzip", "Content-Length": str(len(body))},
            )
        else:
            response = PlainTextResponse("Hello, world!")

        response.headers["Vary"] = "Accept-Encoding"
        await response(scope, receive, send)

    spy = CacheSpy(gzippable_app)
    app = CacheMiddleware(spy, cache=cache)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        r = await client.get("/", headers={"accept-encoding": "gzip"})
        assert spy.misses == 1
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert r.headers["content-encoding"] == "gzip"
        assert "Expires" in r.headers
        assert "Cache-Control" in r.headers

        # Different "Accept-Encoding" header => the cached result
        # for "Accept-Encoding: gzip" should not be used.
        r1 = await client.get("/", headers={"accept-encoding": "identity"})
        assert spy.misses == 2
        assert r1.status_code == 200
        assert r1.text == "Hello, world!"
        assert "Expires" in r.headers
        assert "Cache-Control" in r.headers

        # This "Accept-Encoding" header has already been seen => we should
        # get a cached response.
        r2 = await client.get("/", headers={"accept-encoding": "gzip"})
        assert spy.misses == 2
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert r2.headers["Content-Encoding"] == "gzip"
        assert "Expires" in r.headers
        assert "Cache-Control" in r.headers
