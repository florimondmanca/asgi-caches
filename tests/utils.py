import contextlib
import logging
import os
import typing

import httpx
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import asgi_caches.utils.logging


async def mock_receive() -> Message:
    raise NotImplementedError  # pragma: no cover


async def mock_send(message: Message) -> None:
    raise NotImplementedError  # pragma: no cover


class CacheSpy:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.misses = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.misses += 1
        await self.app(scope, receive, send)


class ComparableStarletteResponse:
    # As of 0.12, Starlette does not provide a '.__eq__()' implementation
    # for responses yet.

    def __init__(self, response: Response) -> None:
        self.response = response

    def __eq__(self, other: typing.Any) -> bool:
        assert isinstance(other, Response)
        return (
            self.response.body == other.body
            and self.response.raw_headers == other.raw_headers
            and self.response.status_code == other.status_code
        )


class ComparableHTTPXResponse:
    # As of 0.7, HTTPX does not provide a '.__eq__()' implementation
    # for responses yet.

    def __init__(self, response: httpx.models.BaseResponse) -> None:
        self.response = response

    def __eq__(self, other: typing.Any) -> bool:
        assert isinstance(other, httpx.models.BaseResponse)
        return (
            self.response.content == other.content
            and self.response.headers == other.headers
            and self.response.status_code == other.status_code
        )


@contextlib.contextmanager
def override_log_level(log_level: str) -> typing.Iterator[None]:
    os.environ["ASGI_CACHES_LOG_LEVEL"] = log_level

    # Force a reload on the logging handlers
    asgi_caches.utils.logging._logger_factory._initialized = False
    asgi_caches.utils.logging.get_logger("asgi_caches")

    try:
        yield
    finally:
        # Reset the logger so we don't have verbose output in all unit tests
        logging.getLogger("asgi_caches").handlers = []
