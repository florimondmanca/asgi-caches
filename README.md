# asgi-caches

[![Build Status](https://travis-ci.com/florimondmanca/asgi-caches.svg?branch=master)](https://travis-ci.com/florimondmanca/asgi-caches)
[![Coverage](https://codecov.io/gh/florimondmanca/asgi-caches/branch/master/graph/badge.svg)](https://codecov.io/gh/florimondmanca/asgi-caches)
[![Package version](https://badge.fury.io/py/asgi-caches.svg)](https://pypi.org/project/asgi-caches)

`asgi-caches` provides middleware and utilities for adding server-side HTTP caching to ASGI applications. It is powered by [async-caches](https://rafalp.github.io/async-caches/), and inspired by Django's cache framework.

**Note**: this project is in an "alpha" status. Several features still need to be implemented, and you should expect breaking API changes across minor versions.

## Features

- Compatible with any ASGI application (e.g. Starlette, FastAPI, Quart, etc.).
- Support for application-wide or per-endpoint caching.
- Ability to fine-tune the cache behavior (TTL, cache control) down to the endpoint level.
- Clean and explicit API enabled by a loose coupling with `async-caches`.
- Fully type annotated.
- 100% test coverage.

## Installation

```bash
pip install asgi-caches
```

## Usage

We'll use this sample [Starlette](https://www.starlete.io) application equipped with an in-memory cache as a supporting example:

```python
from caches import Cache
from starlette.applications import Starlette

app = Starlette()
cache = Cache("locmem://null", key_prefix="my-app", ttl=2 * 60)
app.add_event_handler("startup", cache.connect)
app.add_event_handler("shutdown", cache.disconnect)
```

### Application-wide caching

To cache all endpoints, wrap the application around `CacheMiddleware`:

```python
from asgi_caches.middleware import CacheMiddleware

app.add_middleware(CacheMiddleware, cache=cache)
```

This middleware applies the `Cache-Control` and `Expires` headers based on the cache `ttl` (see also [Time to live](#time-to-live)). These headers tell the browser how and for how long it should cache responses.

If you have multiple middleware, read [Order of middleware](#order-of-middleware) to know at which point in the stack `CacheMiddleware` should be applied.

### Per-endpoint caching

If your ASGI web framework supports a notion of endpoints (a.k.a. "routes"), you can specify the cache policy on a given endpoint using the `@cached` decorator. This works regardless of whether `CacheMiddleware` is present.

```python
from starlette.endpoints import HTTPEndpoint
from asgi_caches.decorators import cached

@app.route("/users/{user_id:int}")
@cached(cache)
class UserDetail(HTTPEndpoint):
    async def get(self, request):
        ...
```

Note that the decorated object should be an ASGI callable. This is why the code snippet above uses a Starlette [endpoint](https://www.starlette.io/endpoints/) (a.k.a. class-based view) instead of a function-based view. (Starlette endpoints implement the ASGI interface, while function-based views don't.)

Note that you can't apply `@cached` to methods of a class either. This is probably fine though, as you shouldn't need to specify which methods support caching: `asgi-caches` will only ever cache "safe" requests, i.e. GET and HEAD.

### Disabling caching (TODO)

To disable caching altogether on a given endpoint, use the `@never_cache` decorator:

```python
from datetime import datetime
from asgi_caches.decorators import never_cache

@app.route("/datetime")
@never_cache
class DateTime(HTTPEndpoint):
    async def get(self, request):
        return JSONResponse({"time": datetime.now().utcformat()})
```

### Time to live

Time to live (TTL) refers to how long (in seconds) a response can stay in the cache before it expires.

Components in `asgi-caches` will use the TTL set on the `Cache` instance by default.

You can override the TTL on a per-view basis by setting the `max-age` cache-control directive (for details, see [Cache control](#cache-control) below):

```python
@app.route("/constant")
@cache_control(max_age=60 * 60)  # Cache for one hour.
class Constant(HTTPEndpoint):
    ...
```

For more information on using TTL, see [Default time to live](https://rafalp.github.io/async-caches/backends/#default-time-to-live) in the `async-caches` documentation.

### Cache control

If you'd like to add extra directives to the [`Cache-Control`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control) header of responses returned by an endpoint, for example to fine-tune how clients should cache them, you can use the `@cache_control()` decorator.

Using `@cache_control()` is often preferable to manually setting the `Cache-Control` header on the response, as it will _add_ directives instead of replacing the existing ones.

If `Cache-Control` is already set on the response, pre-existing directives may be overridden by those passed `@cache_control()`. For example, if the response contains `Cache-Control: no-transform, must-revalidate` and you use `@cache_control(must_revalidate=False)`, then the `must-revalidate` directive will not be included in the final header.

In particular, this allows you to override the TTL using `@cache_control(max_age=...)`. Note, however, that the minimum of the existing `max-age` (if set) and the one passed to `@cache_control()` will be used.

**Note**: setting the `public` and `private` directives is not supported yet -- [Cache privacy](#cache-privacy).

**Note**: `@cache_control()` is independant of `CacheMiddleware` and `@cached`: applying it will _not_ result in storing responses in the server-side cache.

```python
from asgi_caches.decorators import cache_control

@app.route("/")
@cache_control(
    # Indicate that cache systems MUST refetch
    # the response once it has expired.
    must_revalidate=True,
    # Indicate that cache systems MUST NOT
    # transform the response (e.g. convert between image formats).
    no_transform=True,
)
class Resource(HTTPEndpoint):
    async def get(self, request):
        ...
```

For a list of valid cache directives, see the [HTTP Cache Directive Registry](https://www.iana.org/assignments/http-cache-directives/http-cache-directives.xhtml) (note that not all apply to responses). For more information on using these directives, see the [MDN web docs on `Cache-Control`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control).

#### Cache privacy (TODO)

One particular use case for `@cache_control()` is cache privacy. There may be multiple intermediate caching systems between your server and your clients (e.g. a CDN, the user's ISP, etc.). If an endpoint returns sensitive user data (e.g. a bank account number), you probably want to tell the cache that this data is private, and should not be cached at all.

You can achieve this by using the `private` cache-control directive:

```python
@app.get("/accounts/{user_id}")
@cache_control(private=True)
class BankAccount(HTTPEndpoint):
    async def get(self, request):
        ...
```

Alternatively, you can explicitly mark a resource as public by passing `public=True`.

Note that `private` and `public` are exclusive (only one of them can be passed).

### Order of middleware

The cache middleware uses the `Vary` header present in responses to know by which request header it should vary the cache. For example, if a response contains `Vary: Accept-Encoding`, a request containing `Accept-Encoding: gzip` won't result in using the same cache entry than a request containing `Accept-Encoding: identity`.

As a result of this mechanism, there are some rules relative to which point in the middleware stack cache middleware should be applied:

- `CacheMiddleware` should be applied _after_ middleware that modifies the `Vary` header. For example:

```python
from starlette.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware)  # Adds 'Accept-Encoding'
app.add_middleware(CacheMiddleware, cache=cache)
```

- Similarly, it should be applied _before_ middleware that may add something to the varying headers of the request. (As a contrived example, if you had a middleware that added `gzip` to `Accept-Encoding` to later decompress the resulting response body, then you'd need to place this middleware _before_ `CacheMiddleware`.)

### Debugging

If you'd like to see more of what `asgi-caches` is doing, for example to investigate a bug, you can turn on debugging logs.

To do this, you can set the `ASGI_CACHES_LOG_LEVEL` environment variable to one of the following values (case insensitive):

- `debug`: general-purpose output on cache hits, cache misses, and storage of responses in the cache.
- `trace`: very detailed output on what operations are performed (e.g. calls to the remote cache system, computation of cache keys, reasons why responses are not cached, etc).

Note that if using [Uvicorn](https://www.uvicorn.org) or another logging-aware program, logs may be activated (perhaps with a different formatting) even if the environment variable is not set. (For example, Uvicorn will activate debug logs when run with `--log-level=debug`.)

Example output when running with [Uvicorn](https://www.uvicorn.org):

```console
$ uvicorn debug.app:app --log-level=debug
INFO:     Started server process [95022]
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Waiting for application startup.
INFO:     Application startup complete.
DEBUG:    cache_lookup MISS
DEBUG:    store_in_cache max_age=120
INFO:     127.0.0.1:59895 - "GET / HTTP/1.1" 200 OK
DEBUG:    cache_lookup HIT
INFO:     127.0.0.1:59897 - "GET / HTTP/1.1" 200 OK
```

## Credits

Due credit goes to the Django developers and maintainers, as a lot of the API and implementation was directly inspired by the [Django cache framework](https://docs.djangoproject.com/en/2.2/topics/cache/).

## License

MIT
