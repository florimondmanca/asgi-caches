import math

from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route, request_response

from asgi_caches.decorators import cache_control
from asgi_caches.middleware import CacheMiddleware
from tests.utils import CacheSpy

from .resources import cache, special_cache


async def _home(request: Request) -> Response:
    return PlainTextResponse("Hello, world!")


home = CacheSpy(request_response(_home))


@cache_control(max_age=30, must_revalidate=True)
class Pi(HTTPEndpoint):
    async def get(self, request: Request) -> Response:
        return JSONResponse({"value": math.pi})


pi = CacheSpy(Pi)


class Exp(HTTPEndpoint):
    async def get(self, request: Request) -> Response:
        return JSONResponse({"value": math.e})


exp = CacheSpy(Exp)


async def sub_home(request: Request) -> Response:
    return PlainTextResponse("Hello, sub world!")


sub_app = CacheSpy(Starlette(routes=[Route("/", sub_home)]))


app = Starlette(
    routes=[
        Route("/", home),
        Route("/pi", CacheMiddleware(pi, cache=cache)),
        Route("/exp", CacheMiddleware(exp, cache=special_cache)),
        Mount("/sub", CacheMiddleware(sub_app, cache=cache)),
    ],
)

spies = {
    "/": home,
    "/pi": pi,
    "/exp": exp,
    "/sub/": sub_app,
}
