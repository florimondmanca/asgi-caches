from caches import Cache
from starlette.requests import Request
from starlette.responses import Response


class ASGICachesException(Exception):
    pass


class RequestNotCachable(ASGICachesException):
    """Raised when a request cannot be cached."""

    def __init__(self, request: Request) -> None:
        super().__init__()
        self.request = request


class ResponseNotCachable(ASGICachesException):
    """Raised when a response cannot be cached."""

    def __init__(self, response: Response) -> None:
        super().__init__()
        self.response = response


class DuplicateCaching(ASGICachesException):
    """
    Raised when more than one cache middleware
    were detected in the middleware stack.
    """


class CacheNotConnected(ASGICachesException):
    """
    Raised when trying to use the cache, but it isn't connected.
    """

    def __init__(self, cache: Cache) -> None:
        super().__init__(
            f"Cache at '{cache.url}' is not connected.\n"
            "HINT: https://rafalp.github.io/async-caches/backends/#connection"
        )
        self.cache = cache
