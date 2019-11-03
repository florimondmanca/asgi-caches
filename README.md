# asgi-caches

`asgi-caches` provides middleware and utilities for adding caching to ASGI applications. It is based on [async-caches](https://rafalp.github.io/async-caches/), and inspired by Django's cache framework.

## Usage

We'll use this sample [Starlette](https://www.starlete.io) application as a supporting example:

```python
from caches import Cache
from starlette.applications import Starlette

app = Starlette()
cache = Cache(key_prefix="my-app", ttl=2 * 60)
app.add_event_handler("startup", cache.connect)
app.add_event_handler("shutdown", cache.disconnect)
```

### Application-wide caching (TODO)

```python
from asgi_caches.middleware import CacheMiddleware

app.add_middleware(CacheMiddleware, cache=cache)
```

### Per-view caching (TODO)

> **Note**: this is currently only available for Starlette (or, more precisely, frameworks whose views have the same signature as Starlette's, i.e. `async (Request) -> Response`).

```python
from asgi_caches.contrib.starlette.decorators import cache_view

@app.route("/users/{user_id:int}")
@cache_view(cache)
async def get_user(request):
    ...
```

To disable caching altogether on a given view, use the `@never_cache` decorator:

```python
from datetime import datetime
from asgi_caches.contrib.starlette.decorators import never_cache

@never_cache
async def my_view(request):
    return JSONResponse({"time": datetime.now().utcformat()})
```

### Time to live (TODO)

Time to live (TTL) refers to how long (in seconds) a response can stay in the cache before it expires.

Components in `asgi-cache` will use whichever TTL is set on the `Cache` instance by default:

```python
# Cache for 2 minutes by default.
cache = Cache(ttl=2 * 60)
```

> See also: [Async Caches: Default time to live](https://rafalp.github.io/async-caches/backends/#default-time-to-live).

You can override the TTL on a per-view basis using the `ttl` parameter, e.g.:

```python
import math
from starlette.responses import JSONResponse

@app.route("/pi")
@cache_view(cache, ttl=None)  # Cache forever
async def get_pi(request):
    return JSONResponse({"value": math.pi})
```

### Cache control (TODO)

You can use the `@cache_control()` decorator to add cache control directives to responses. This decorator will set the appropriate headers automatically (e.g. [`Cache-Control`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control)).

One typical use case is cache privacy. If your view returns sensitive information to clients (e.g. a bank account number), you will probably want to mark its cache as `private`. This is how to do it:

```python
from asgi_caches.contrib.starlette.decorators import cache_control

@cache_control(private=True)
async def get_bank_account(request):
    ...
```

Alternatively, you can explicitly mark a cache as public with `public=True`.

(Note that the `public` and `private` directives are mutually exclusive. The decorator ensures that one is removed if the other is set, and vice versa.)

Besides, `@cache_control()` accepts any valid `Cache-Control` directives. For example, [`max-age`](https://tools.ietf.org/html/rfc7234.html#section-5.2.2.8) controls the amount of time clients should cache the response:

```python
from asgi_caches.contrib.starlette.decorators import cache_control

@cache_control(max_age=3600)
async def my_view(request):
    ...
```

Other example directives:

- `no_transform=True`
- `must_revalidate=True`
- `stale_while_revalidate=num_seconds`

See [RFC7234](https://tools.ietf.org/html/rfc7234.html) (Caching) for more information, and the [HTTP Cache Directive Registry](https://www.iana.org/assignments/http-cache-directives/http-cache-directives.xhtml) for the list of valid cache directives (note not all apply to responses).

## License

MIT
