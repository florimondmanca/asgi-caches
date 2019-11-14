import typing

import httpx
import pytest
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from asgi_caches.middleware import CacheControlMiddleware
from tests.utils import mock_receive, mock_send


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "initial, kwargs, result",
    [
        pytest.param(None, {}, None, id="no-op"),
        pytest.param("stale-if-error=30", {}, "stale-if-error=30", id="copy-initial"),
        pytest.param(None, {"stale_if_error": 60}, "stale-if-error=60", id="add-value"),
        pytest.param(
            "stale-if-error=30",
            {"stale_if_error": 60},
            "stale-if-error=60",
            id="override-value",
        ),
        pytest.param("max-stale=60", {"max_stale": False}, None, id="remove-value",),
        pytest.param(None, {"must_revalidate": True}, "must-revalidate", id="add-true"),
        pytest.param(None, {"must_revalidate": False}, None, id="add-false"),
        pytest.param(
            "must-revalidate", {"must_revalidate": False}, None, id="remove-false",
        ),
        pytest.param(
            "must-revalidate, max-stale=60, only-if-cached",
            {"stale_if_error": 60, "no_transform": True, "max_stale": False},
            "must-revalidate, only-if-cached, stale-if-error=60, no-transform",
            id="mixed",
        ),
        pytest.param(
            "max-age=60", {"max_age": 30}, "max-age=30", id="override-max-age-1"
        ),
        pytest.param(
            "max-age=30", {"max_age": 60}, "max-age=30", id="override-max-age-2"
        ),
        pytest.param(None, {"public": True}, NotImplementedError),
        pytest.param(None, {"private": True}, NotImplementedError),
    ],
)
async def test_cache_control_middleware(
    initial: typing.Optional[str],
    kwargs: dict,
    result: typing.Optional[typing.Union[str, typing.Type[BaseException]]],
) -> None:
    app: ASGIApp = PlainTextResponse(
        "Hello, world!", headers={"Cache-Control": initial} if initial else {},
    )
    app = CacheControlMiddleware(app, **kwargs)
    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with client:
        if result is NotImplementedError:
            with pytest.raises(NotImplementedError):
                await client.get("/")
        else:
            r = await client.get("/")
            assert r.status_code == 200
            assert r.text == "Hello, world!"
            if not result:
                assert "Cache-Control" not in r.headers
            else:
                assert r.headers["Cache-Control"] == result


@pytest.mark.asyncio
async def test_not_http() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "lifespan"

    app = CacheControlMiddleware(app)
    await app({"type": "lifespan"}, mock_receive, mock_send)
