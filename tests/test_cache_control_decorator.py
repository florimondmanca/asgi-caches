import httpx
import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import Receive, Scope, Send

from asgi_caches.decorators import cache_control


@pytest.mark.asyncio
async def test_cache_control_decorator() -> None:
    @cache_control(stale_if_error=60, must_revalidate=True)
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        response = PlainTextResponse("Hello, world!")
        await response(scope, receive, send)

    client = httpx.AsyncClient(app=app, base_url="http://testserver")

    async with client:
        r = await client.get("/")
        assert r.status_code == 200
        assert r.text == "Hello, world!"
        assert r.headers["Cache-Control"] == "stale-if-error=60, must-revalidate"


@pytest.mark.asyncio
async def test_decorate_starlette_view() -> None:
    with pytest.raises(ValueError):

        @cache_control(stale_if_error=60)
        async def home(request: Request) -> Response:
            ...  # pragma: no cover
