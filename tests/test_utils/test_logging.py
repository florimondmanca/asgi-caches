import typing

import httpx
import pytest
from caches import Cache
from starlette.responses import PlainTextResponse

from asgi_caches.middleware import CacheMiddleware
from tests.utils import override_log_level


@pytest.mark.asyncio
async def test_logs_debug(capsys: typing.Any) -> None:
    cache = Cache("locmem://null", ttl=2 * 60)
    app = CacheMiddleware(PlainTextResponse("Hello, world!"), cache=cache)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        with override_log_level("debug"):
            await client.get("/")
            await client.get("/")

    stderr = capsys.readouterr().err
    miss_line, store_line, hit_line, *_ = stderr.split("\n")
    assert "cache_lookup MISS" in miss_line
    assert "store_in_cache max_age=120" in store_line
    assert "cache_lookup HIT" in hit_line
    assert "get_from_cache request.url='http://testserver/" not in stderr


@pytest.mark.asyncio
async def test_logs_trace(capsys: typing.Any) -> None:
    cache = Cache("locmem://null", ttl=2 * 60)
    app = CacheMiddleware(PlainTextResponse("Hello, world!"), cache=cache)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with cache, client:
        with override_log_level("trace"):
            await client.get("/")

    stderr = capsys.readouterr().err
    assert "cache_lookup MISS" in stderr
    assert "get_from_cache request.url='http://testserver/" in stderr
