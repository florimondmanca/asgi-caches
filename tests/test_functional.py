import math
import typing

import httpx
import pytest
from caches import Cache
from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from asgi_caches.decorators import cache_control, cached
from asgi_caches.middleware import CacheMiddleware

cache = Cache("locmem://null", ttl=2 * 60)
app = Starlette()
pi_calls = 0


@app.route("/")
async def home(request: Request) -> Response:
    return PlainTextResponse("Hello, world!")


@app.route("/pi")
@cached(cache)
@cache_control(must_revalidate=True)
class Pi(HTTPEndpoint):
    async def get(self, request: Request) -> Response:
        global pi_calls
        pi_calls += 1
        return JSONResponse({"value": math.pi})


sub_app = Starlette()
sub_app.add_middleware(CacheMiddleware, cache=cache)


@sub_app.route("/")
async def sub_home(request: Request) -> Response:
    return PlainTextResponse("Hello, sub world!")


app.mount("/sub", sub_app)


@pytest.fixture(name="client")
async def fixture_client() -> typing.AsyncIterator[httpx.AsyncClient]:
    client = httpx.AsyncClient(app=app, base_url="http://testserver")
    async with cache, client:
        yield client


@pytest.mark.asyncio
async def test_caching(client: httpx.AsyncClient) -> None:
    r = await client.get("/")
    assert r.status_code == 200
    assert r.text == "Hello, world!"
    assert "Expires" not in r.headers
    assert "Cache-Control" not in r.headers

    r = await client.get("/pi")
    assert r.status_code == 200
    assert r.json() == {"value": math.pi}
    assert pi_calls == 1
    assert "Expires" in r.headers
    assert "Cache-Control" in r.headers
    assert r.headers["Cache-Control"] == "must-revalidate, max-age=120"

    r = await client.get("/pi")
    assert pi_calls == 1

    r = await client.get("/sub/")
    assert r.status_code == 200
    assert r.text == "Hello, sub world!"
    assert "Expires" in r.headers
    assert "Cache-Control" in r.headers
    assert r.headers["Cache-Control"] == "max-age=120"
