# User Guide

## Getting started

`asgi-caches` uses `async-caches` to interact with cache backends. This means you'll first need to [setup a `Cache`](https://rafalp.github.io/async-caches/backends/) and make sure it is [connected](https://rafalp.github.io/async-caches/backends/#connection) for when your application responds to requests.

Here's an example setup with [Starlette](https://www.starlete.io) and an in-memory cache with a default time to live of 2 minutes:

```python
from caches import Cache
from starlette.applications import Starlette

cache = Cache("locmem://null", ttl=2 * 60)

app = Starlette(on_startup=[cache.connect], on_shutdown=[cache.disconnect])
```

## Enabling caching

There are two ways to enable HTTP caching on an application: on an entire application, or on a specific endpoint. Both rely on `CacheMiddleware`, an ASGI middleware.

!!! note
    You cannot use endpoint-level caching if application-level caching is enabled.
    
    As a rule of thumb, you should explicitly specify which endpoints should be cached as soon as you need anything more granular than caching all endpoints on the application.

### Application-wide caching

To cache all endpoints, wrap the application around `CacheMiddleware`:

```python
from asgi_caches.middleware import CacheMiddleware

app = CacheMiddleware(app, cache=cache)
```

!!! hint
    If your ASGI web framework provides a specific way of adding middleware, you'll probably want to use it instead of wrapping the app directly.

This middleware applies the `Cache-Control` and `Expires` headers based on the cache `ttl` (see also [Time to live](#time-to-live)). These headers tell the browser how and for how long it should cache responses.

If you have multiple middleware, read [Order of middleware](#order-of-middleware) to know at which point in the stack `CacheMiddleware` should be applied.

### Per-endpoint caching

If your ASGI web framework supports a notion of endpoints (a.k.a. "routes"), you can specify the cache policy on a given endpoint using the `@cached` decorator. This works regardless of whether `CacheMiddleware` is present.

Starlette example:

```python
from asgi_caches.decorators import cached
from starlette.endpoints import HTTPEndpoint

@cached(cache)
class UserDetail(HTTPEndpoint):
    async def get(self, request):
        ...
```

Note that the decorated object should be an ASGI callable. This is why the code snippet above uses a Starlette [endpoint](https://www.starlette.io/endpoints/) (a.k.a. class-based view) instead of a function-based view. (Starlette endpoints implement the ASGI interface, while function-based views don't.)

Note that you can't apply `@cached` to methods of a class either. This is probably fine though, as you shouldn't need to specify which methods support caching: `asgi-caches` will only ever cache "safe" requests, i.e. GET and HEAD.


## Caching fine-tuning

### Time to live

Time to live (TTL) refers to how long (in seconds) a response can stay in the cache before it expires.

Components in `asgi-caches` will use the TTL set on the `Cache` instance by default.

You can override the TTL on a per-view basis by setting the `max-age` cache-control directive (for details, see [Cache control](#cache-control) below).

Starlette example:

```python
from asgi_caches.decorators import cache_control
from starlette.endpoints import HTTPEndpoint

@cache_control(max_age=60 * 60)  # Cache for one hour.
class Constant(HTTPEndpoint):
    ...
```

For more information on using TTL, see [Default time to live](https://rafalp.github.io/async-caches/backends/#default-time-to-live) in the `async-caches` documentation.

### Cache-Control

If you'd like to add extra directives to the [`Cache-Control`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control) header of responses returned by an endpoint, for example to fine-tune how clients should cache them, you can use the `@cache_control()` decorator.

Using `@cache_control()` is often preferable to manually setting the `Cache-Control` header on the response, as it will _add_ directives instead of replacing the existing ones.

If `Cache-Control` is already set on the response, pre-existing directives may be overridden by those passed `@cache_control()`. For example, if the response contains `Cache-Control: no-transform, must-revalidate` and you use `@cache_control(must_revalidate=False)`, then the `must-revalidate` directive will not be included in the final header.

In particular, this allows you to override the TTL using `@cache_control(max_age=...)`. Note, however, that the minimum of the existing `max-age` (if set) and the one passed to `@cache_control()` will be used.

!!! note
    Setting the `public` and `private` directives is not supported yet -- [Cache privacy](#cache-privacy).

!!! tip
    `@cache_control()` is independant of `CacheMiddleware` and `@cached`: applying it will _not_ result in storing responses in the server-side cache.

Starlette example:

```python
from asgi_caches.decorators import cache_control
from starlette.endpoints import HTTPEndpoint

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

#### Cache privacy

!!! warning
    This section documents functionality that has not been implemented yet.

One particular use case for `@cache_control()` is cache privacy. There may be multiple intermediate caching systems between your server and your clients (e.g. a CDN, the user's ISP, etc.). If an endpoint returns sensitive user data (e.g. a bank account number), you probably want to tell the cache that this data is private, and should not be cached at all.

You can achieve this by using the `private` cache-control directive:

```python
from asgi_caches.decorators import cache_control
from starlette.endpoints import HTTPEndpoint

@cache_control(private=True)
class BankAccount(HTTPEndpoint):
    async def get(self, request):
        ...
```

Alternatively, you can explicitly mark a resource as public by passing `public=True`.

!!! note
    `private` and `public` are exclusive (only one of them can be passed).

### Disabling caching

!!! warning
    This section documents functionality that has not been implemented yet.

To disable caching altogether on a given endpoint, you can use the `@never_cache` decorator.

Starlette example:

```python
from datetime import datetime
from asgi_caches.decorators import never_cache
from starlette.endpoints import HTTPEndpoint

@never_cache
class DateTime(HTTPEndpoint):
    async def get(self, request):
        return JSONResponse({"time": datetime.now().utcformat()})
```

## Order of middleware

The cache middleware uses the `Vary` header present in responses to know by which request header it should vary the cache. For example, if a response contains `Vary: Accept-Encoding`, a request containing `Accept-Encoding: gzip` won't result in using the same cache entry than a request containing `Accept-Encoding: identity`.

As a result of this mechanism, there are some rules relative to which point in the middleware stack cache middleware should be applied:

- `CacheMiddleware` should be applied _after_ middleware that modifies the `Vary` header. For example:

```python
from starlette.middleware.gzip import GZipMiddleware

app = GZipMiddleware(app)  # Adds 'Accept-Encoding'
app = CacheMiddleware(app, cache=cache)
```

- Similarly, it should be applied _before_ middleware that may add something to the varying headers of the request. For example, if you had a middleware that added authentication session cookies, and `Cookie` is present in the `Vary` header of responses, then you'd need to place `CacheMiddleware` _before_ this middleware.

## Logging

`asgi-caches` provides logs that contain detail about what is going on: cache hits, cache misses, cache key derivation, etc. These logs are particularly useful when investigating bugs or unexpected behavior.

If using [Uvicorn](https://www.uvicorn.org) or another logging-aware program, `DEBUG` and `TRACE` logs should be activated when serving with the corresponding log level.

For example, Uvicorn should show `asgi-caches` debug logs when run with `--log-level=debug`:

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

If you need to manually activate logs, you can set the `ASGI_CACHES_LOG_LEVEL` environment variable to one of the following values (case insensitive):

- `debug`: general-purpose output on cache hits, cache misses, and storage of responses in the cache.
- `trace`: very detailed output on all operations performed. This includes calls to the remote cache system, computation of cache keys, reasons why responses are not cached, etc.
