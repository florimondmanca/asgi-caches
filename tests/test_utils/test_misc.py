import typing

import pytest
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from asgi_caches.utils.misc import is_asgi3


class CallableClass:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ...  # pragma: no cover


callable_instance = CallableClass()


class AwaitableClass:
    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ...  # pragma: no cover

    def __await__(self) -> None:
        ...  # pragma: no cover


async def async_function(scope: Scope, receive: Receive, send: Send) -> None:
    ...  # pragma: no cover


async def view(request: Request) -> Response:
    ...  # pragma: no cover


@pytest.mark.parametrize(
    "app, output",
    [
        (CallableClass, False),
        (callable_instance, True),
        (AwaitableClass, True),
        (async_function, True),
        (view, False),
        (object(), False),
    ],
)
def test_is_asgi3(app: typing.Any, output: bool) -> None:
    assert is_asgi3(app) == output
