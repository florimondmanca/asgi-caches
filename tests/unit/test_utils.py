import datetime as dt
import typing

import pytest
from caches import Cache
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.types import Scope

from asgi_caches.exceptions import RequestNotCachable, ResponseNotCachable
from asgi_caches.utils import (
    deserialize_response,
    get_cache_key,
    get_from_cache,
    store_in_cache,
)
from tests.utils import ComparableResponse

pytestmark = pytest.mark.asyncio


@pytest.fixture(name="cache")
async def fixture_cache() -> typing.AsyncIterator[Cache]:
    async with Cache("locmem://null") as cache:
        yield cache


@pytest.fixture(name="short_cache")
async def fixture_short_cache() -> typing.AsyncIterator[Cache]:
    async with Cache("locmem://null", ttl=2 * 60) as cache:
        yield cache


@pytest.mark.parametrize("method", ("GET", "HEAD"))
async def test_get_from_emtpy_cache(cache: Cache, method: str) -> None:
    scope: Scope = {
        "type": "http",
        "method": method,
        "path": "/path",
        "headers": [],
    }
    request = Request(scope)
    response = await get_from_cache(request, cache=cache)
    assert response is None


@pytest.mark.parametrize(
    "method", ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE")
)
async def test_non_cachable_methods(cache: Cache, method: str) -> None:
    scope: Scope = {
        "type": "http",
        "method": method,
        "path": "/path",
        "headers": [],
    }
    request = Request(scope)
    with pytest.raises(RequestNotCachable):
        await get_from_cache(request, cache=cache)


async def test_store_in_cache(cache: Cache) -> None:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/path",
        "headers": [],
    }
    request = Request(scope)
    response = PlainTextResponse("Hello, world!")
    assert await get_cache_key(request, method="GET", cache=cache) is None

    await store_in_cache(response, request=request, cache=cache)

    key = await get_cache_key(request, method="GET", cache=cache)
    assert key is not None

    cached_response = deserialize_response(await cache.get(key))
    assert ComparableResponse(cached_response) == response


@pytest.mark.parametrize(
    "status_code", (201, 202, 204, 301, 307, 308, 400, 401, 403, 500, 502, 503)
)
async def test_non_cachable_status_codes(cache: Cache, status_code: int) -> None:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/path",
        "headers": [],
    }
    request = Request(scope)
    response = PlainTextResponse("Hello, world!", status_code=status_code)
    with pytest.raises(ResponseNotCachable):
        await store_in_cache(response, request=request, cache=cache)


async def test_get_from_cache(cache: Cache) -> None:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/path",
        "headers": [],
    }
    request = Request(scope)
    response = PlainTextResponse("Hello, world!")
    await store_in_cache(response, request=request, cache=cache)

    cached_response = await get_from_cache(request, cache=cache)
    assert cached_response is not None
    assert ComparableResponse(cached_response) == response
    assert "Expires" in cached_response.headers
    assert "Cache-Control" in cached_response.headers


async def test_default_max_age(cache: Cache) -> None:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/path",
        "headers": [],
    }
    request = Request(scope)
    response = PlainTextResponse("Hello, world!")
    await store_in_cache(response, request=request, cache=cache)

    cached_response = await get_from_cache(request, cache=cache)
    assert cached_response is not None
    now = dt.datetime.utcnow()
    http_date_fmt = "%a, %d %b %Y %H:%M:%S GMT"
    expires = dt.datetime.strptime(cached_response.headers["Expires"], http_date_fmt)
    delta: dt.timedelta = expires - now
    one_year = int(dt.timedelta(days=365).total_seconds())
    assert delta.total_seconds() == pytest.approx(one_year)
    assert cached_response.headers["Cache-Control"] == f"max-age={one_year}"


async def test_cache_ttl_max_age(short_cache: Cache) -> None:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/path",
        "headers": [],
    }
    request = Request(scope)
    response = PlainTextResponse("Hello, world!")
    await store_in_cache(response, request=request, cache=short_cache)

    cached_response = await get_from_cache(request, cache=short_cache)
    assert cached_response is not None
    now = dt.datetime.utcnow()
    http_date_fmt = "%a, %d %b %Y %H:%M:%S GMT"
    expires = dt.datetime.strptime(cached_response.headers["Expires"], http_date_fmt)
    delta: dt.timedelta = expires - now
    assert delta.total_seconds() == pytest.approx(short_cache.ttl, rel=1e-2)
    assert cached_response.headers["Cache-Control"] == f"max-age={short_cache.ttl}"


async def test_get_from_cache_head(cache: Cache) -> None:
    scope: Scope = {
        "type": "http",
        "method": "HEAD",
        "path": "/path",
        "headers": [],
    }
    request = Request(scope)
    response = PlainTextResponse("Hello, world!")
    await store_in_cache(response, request=request, cache=cache)

    cached_response = await get_from_cache(request, cache=cache)
    assert cached_response is not None
    assert ComparableResponse(cached_response) == response


async def test_get_from_cache_different_path(cache: Cache) -> None:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/path",
        "headers": [],
    }
    request = Request(scope)
    response = PlainTextResponse("Hello, world!")
    await store_in_cache(response, request=request, cache=cache)

    other_scope = {**scope, "path": "/other_path"}
    other_request = Request(other_scope)
    cached_response = await get_from_cache(other_request, cache=cache)
    assert cached_response is None


async def test_get_from_cache_vary(cache: Cache) -> None:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/path",
        "headers": [[b"accept-encoding", b"gzip, deflate"]],
    }
    request = Request(scope)
    # Response indicates that contents of the response at this URL may *vary*
    # depending on the "Accept-Encoding" header sent in the request.
    response = PlainTextResponse("Hello, world!", headers={"Vary": "Accept-Encoding"})
    await store_in_cache(response, request=request, cache=cache)

    # Let's use a different "Accept-Encoding" header,
    # and check that no cached response is found.
    other_scope = {**scope, "headers": [[b"accept-encoding", b"identity"]]}
    other_request = Request(other_scope)
    cached_response = await get_from_cache(other_request, cache=cache)
    assert cached_response is None
