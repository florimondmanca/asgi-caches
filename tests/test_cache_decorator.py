import httpx
import pytest
from caches import Cache
from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import Receive, Scope, Send

from asgi_caches.decorators import cached
from asgi_caches.middleware import CacheMiddleware
from tests.utils import CacheSpy


@pytest.mark.asyncio
async def test_decorator_raw_asgi() -> None:
    cache = Cache("locmem://null", ttl=2 * 60)

    @cached(cache)
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        response = PlainTextResponse("Hello, world!")
        await response(scope, receive, send)

    spy = app.app = CacheSpy(app.app)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        assert spy.misses == 0

        r = await client.get("/")
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert "Expires" in r.headers
        assert "Cache-Control" in r.headers
        assert spy.misses == 1

        r = await client.get("/")
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert "Expires" in r.headers
        assert "Cache-Control" in r.headers
        assert spy.misses == 1


@pytest.mark.asyncio
async def test_decorator_starlette_endpoint() -> None:
    app = Starlette()
    cache = Cache("locmem://null", ttl=2 * 60)

    @cached(cache)
    class CachedHome(HTTPEndpoint):
        async def get(self, request: Request) -> Response:
            return PlainTextResponse("Hello, world!")

    class UncachedUsers(HTTPEndpoint):
        async def get(self, request: Request) -> Response:
            return PlainTextResponse("Hello, users!")

    assert isinstance(CachedHome, CacheMiddleware)
    spy = CachedHome.app = CacheSpy(CachedHome.app)
    users_spy = CacheSpy(UncachedUsers)

    app.add_route("/", CachedHome)
    app.add_route("/users", users_spy)

    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        assert spy.misses == 0

        r = await client.get("/")
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert "Expires" in r.headers
        assert "Cache-Control" in r.headers
        assert spy.misses == 1

        r = await client.get("/")
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert "Expires" in r.headers
        assert "Cache-Control" in r.headers
        assert spy.misses == 1

        assert users_spy.misses == 0

        r = await client.get("/users")
        assert r.status_code == 200
        assert r.text == "Hello, users!"
        assert "Expires" not in r.headers
        assert "Cache-Control" not in r.headers
        assert users_spy.misses == 1

        r = await client.get("/users")
        assert r.status_code == 200
        assert r.text == "Hello, users!"
        assert "Expires" not in r.headers
        assert "Cache-Control" not in r.headers
        assert users_spy.misses == 2


@pytest.mark.asyncio
async def test_decorate_starlette_view() -> None:
    cache = Cache("locmem://null", ttl=2 * 60)

    with pytest.raises(ValueError):

        @cached(cache)
        async def home(request: Request) -> Response:
            ...  # pragma: no cover
