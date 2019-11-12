# asgi-caches

[![Build Status](https://travis-ci.com/florimondmanca/asgi-caches.svg?branch=master)](https://travis-ci.com/florimondmanca/asgi-caches)
[![Coverage](https://codecov.io/gh/florimondmanca/asgi-caches/branch/master/graph/badge.svg)](https://codecov.io/gh/florimondmanca/asgi-caches)
[![Package version](https://badge.fury.io/py/asgi-caches.svg)](https://pypi.org/project/asgi-caches)

`asgi-caches` provides middleware and utilities for adding caching to ASGI applications. It is powered by [async-caches](https://rafalp.github.io/async-caches/), and inspired by Django's cache framework.

**Note**: this project is in an "alpha" status. Several features still need to be implemented.

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

### Per-endpoint caching (TODO)

You can specify the cache policy on a given endpoint using the `@cached` decoraotr:

```python
from starlette.endpoints import HTTPEndpoint
from asgi_caches.decorators import cached

@app.route("/users/{user_id:int}")
@cached(cache)
class UserDetail(HTTPEndpoint):
    async def get(self, request):
        ...
```

Note that since the `@cached` decorator actually works on any ASGI application, the snippet above uses a Starlette [endpoint](https://www.starlette.io/endpoints/) instead of a function-based view. (As a consequence, applying `@cached` to methods of an endpoint class is not supported. This should not be a problem, because caching is only ever applied to GET and HEAD operations.)

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

Components in `asgi-caches` will use whichever TTL is set on the `Cache` instance by default:

```python
# Cache for 2 minutes by default.
cache = Cache("locmem://null", ttl=2 * 60)
```

(See also [Default time to live](https://rafalp.github.io/async-caches/backends/#default-time-to-live) in the `async-caches` documentation.)

(TODO) You can override the TTL on a per-view basis using the `ttl` parameter, e.g.:

```python
import math
from starlette.responses import JSONResponse
from asgi_caches.decorators import cached

@app.route("/pi")
@cached(cache, ttl=None)  # Cache forever
class Pi(HTTPEndpoint):
    async def get(self, request):
        return JSONResponse({"value": math.pi})
```

### Cache control (TODO)

You can use the `@cache_control()` decorator to add cache control directives to responses. This decorator will set the appropriate headers automatically (e.g. [`Cache-Control`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control)).

One typical use case is cache privacy. If your view returns sensitive information to clients (e.g. a bank account number), you will probably want to mark its cache as `private`. This is how to do it:

```python
from asgi_caches.decorators import cache_control

@app.route("/accounts/{account_id}")
@cache_control(private=True)
class BankAccountDetail(HTTPEndpoint):
    async def get(self, request):
        ...
```

Alternatively, you can explicitly mark a cache as public with `public=True`.

(Note that the `public` and `private` directives are mutually exclusive. The decorator ensures that one is removed if the other is set, and vice versa.)

Besides, `@cache_control()` accepts any valid `Cache-Control` directives. For example, [`max-age`](https://tools.ietf.org/html/rfc7234.html#section-5.2.2.8) controls the amount of time clients should cache the response:

```python
from asgi_caches.decorators import cache_control

@app.route("/weather_reports/today")
@cache_control(max_age=3600)
class DailyWeatherReport(HTTPEndpoint):
    async def get(self, request):
        ...
```

Other example directives:

- `no_transform=True`
- `must_revalidate=True`
- `stale_while_revalidate=num_seconds`

See [RFC7234](https://tools.ietf.org/html/rfc7234.html) (Caching) for more information, and the [HTTP Cache Directive Registry](https://www.iana.org/assignments/http-cache-directives/http-cache-directives.xhtml) for the list of valid cache directives (note not all apply to responses).

### Order of middleware

The cache middleware uses the `Vary` header present in responses to know by which request header it should vary the cache. For example, if a response contains `Vary: Accept-Encoding`, a request containing `Accept-Encoding: gzip` won't result in using the same cache entry than a request containing `Accept-Encoding: identity`.

As a result of this mechanism, there are some rules relative to which point in the middleware stack cache middleware should be applied:

- `CacheMiddleware` should be applied *after* middleware that modifies the `Vary` header. For example:

```python
from starlette.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware)  # Adds 'Accept-Encoding'
app.add_middleware(CacheMiddleware, cache=cache)
```

- Similarly, it should be applied *before* middleware that may add something to the varying headers of the request. (As a contrived example, if you had a middleware that added `gzip` to `Accept-Encoding` to later decompress the resulting response body, then you'd need to place this middleware *before* `CacheMiddleware`.)

## Debugging

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
