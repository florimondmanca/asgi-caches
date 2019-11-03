# asgi-caches

[![Build Status](https://travis-ci.com/florimondmanca/asgi-caches.svg?branch=master)](https://travis-ci.com/florimondmanca/asgi-caches)
[![Coverage](https://codecov.io/gh/florimondmanca/asgi-caches/branch/master/graph/badge.svg)](https://codecov.io/gh/florimondmanca/asgi-caches)
[![Package version](https://badge.fury.io/py/asgi-caches.svg)](https://pypi.org/project/asgi-caches)

`asgi-caches` provides middleware and utilities for adding caching to ASGI applications. It is based on [async-caches](https://rafalp.github.io/async-caches/), and inspired by Django's cache framework.

> **Note**: this project is in a "planning" status. Most of the features still need to be implemented.

## Features

- Compatible with any ASGI application (e.g. Starlette, FastAPI, Quart, etc.).
- Support for application-wide or per-endpoint caching.
- Ability to fine-tune the cache behavior (TTL, cache control) down to the endpoint level.
- Clean and explicit API enabled by a loose coupling with `async-caches`.
- Fully type annotated.
- 100% test coverage.

## Usage

We'll use this sample [Starlette](https://www.starlete.io) application as a supporting example:

```python
from caches import Cache
from starlette.applications import Starlette

app = Starlette()
cache = Cache("locmem://null", key_prefix="my-app", ttl=2 * 60)
app.add_event_handler("startup", cache.connect)
app.add_event_handler("shutdown", cache.disconnect)
```

### Application-wide caching (TODO)

```python
from asgi_caches.middleware import CacheMiddleware

app.add_middleware(CacheMiddleware, cache=cache)
```

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

### Time to live (TODO)

Time to live (TTL) refers to how long (in seconds) a response can stay in the cache before it expires.

Components in `asgi-caches` will use whichever TTL is set on the `Cache` instance by default:

```python
# Cache for 2 minutes by default.
cache = Cache(ttl=2 * 60)
```

(See also [Default time to live](https://rafalp.github.io/async-caches/backends/#default-time-to-live) in the `async-caches` documentation.)

You can override the TTL on a per-view basis using the `ttl` parameter, e.g.:

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

## Credits

Due credit goes to the Django developers and maintainers, as a lot of the API and implementation was directly inspired by the [Django cache framework](https://docs.djangoproject.com/en/2.2/topics/cache/).

## License

MIT
