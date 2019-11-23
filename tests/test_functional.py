import importlib
import math
import typing

import httpx
import pytest
from starlette.types import ASGIApp

from tests.examples.resources import cache, special_cache
from tests.utils import CacheSpy

# TIP: use 'pytest -k <id>' to run tests for a given example application only.
EXAMPLES = [
    pytest.param("tests.examples.starlette", id="starlette"),
]


@pytest.fixture(name="app", params=EXAMPLES)
def fixture_app(request: typing.Any) -> ASGIApp:
    module: typing.Any = importlib.import_module(request.param)
    return module.app


@pytest.fixture(name="spies", params=EXAMPLES)
def fixture_spies(request: typing.Any) -> ASGIApp:
    module: typing.Any = importlib.import_module(request.param)
    return module.spies


@pytest.fixture(name="client")
async def fixture_client(app: ASGIApp) -> typing.AsyncIterator[httpx.AsyncClient]:
    client = httpx.AsyncClient(app=app, base_url="http://testserver")
    async with cache, special_cache, client:
        yield client


@pytest.mark.asyncio
async def test_caching(
    client: httpx.AsyncClient, spies: typing.Dict[str, CacheSpy]
) -> None:
    r = await client.get("/")
    assert r.status_code == 200
    assert r.text == "Hello, world!"
    assert spies["/"].misses == 1
    assert "Expires" not in r.headers
    assert "Cache-Control" not in r.headers

    r = await client.get("/")
    assert spies["/"].misses == 2

    r = await client.get("/pi")
    assert r.status_code == 200
    assert r.json() == {"value": math.pi}
    assert spies["/pi"].misses == 1
    assert "Expires" in r.headers
    assert "Cache-Control" in r.headers
    assert r.headers["Cache-Control"] == "max-age=30, must-revalidate"

    r = await client.get("/pi")
    assert spies["/pi"].misses == 1

    r = await client.get("/sub/")
    assert r.status_code == 200
    assert r.text == "Hello, sub world!"
    assert spies["/sub/"].misses == 1
    assert "Expires" in r.headers
    assert "Cache-Control" in r.headers
    assert r.headers["Cache-Control"] == "max-age=120"

    await client.get("/sub/")
    assert spies["/sub/"].misses == 1

    r = await client.get("/exp")
    assert r.status_code == 200
    assert r.json() == {"value": math.e}
    assert spies["/exp"].misses == 1
    assert "Expires" in r.headers
    assert "Cache-Control" in r.headers
    assert r.headers["Cache-Control"] == "max-age=60"

    r = await client.get("/exp")
    assert spies["/exp"].misses == 1
