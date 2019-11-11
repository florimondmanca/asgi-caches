import typing

import httpx
from starlette.responses import Response
from starlette.types import Message


async def mock_receive() -> Message:
    raise NotImplementedError  # pragma: no cover


async def mock_send(message: Message) -> None:
    raise NotImplementedError  # pragma: no cover


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
