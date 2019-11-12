import functools
import typing

from caches import Cache
from starlette.types import ASGIApp

from .middleware import CacheMiddleware
from .utils.misc import is_asgi3


def cached(cache: Cache) -> typing.Callable:
    """
    Decorator for ASGI endpoints that tries to get the response from the cache,
    or populates the cache if the response isn't cached yet.

    This decorator provides the same behavior than `CacheMiddleware`,
    but at an endpoint level.

    Raises 'ValueError' if the wrapped callable isn't an ASGI application.
    """

    def wrap(app: ASGIApp) -> ASGIApp:
        if not is_asgi3(app):
            raise ValueError(
                f"{app!r} does not seem to be an ASGI3 callable. "
                "Did you try to apply this decorator to a framework-specific view "
                "function? (It can only be applied to ASGI callables.)"
            )
        wrapper = CacheMiddleware(app, cache=cache)
        functools.update_wrapper(wrapper, app)
        return wrapper

    return wrap
