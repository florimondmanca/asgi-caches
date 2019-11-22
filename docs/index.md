# Introduction

`asgi-caches` provides middleware and utilities for adding server-side HTTP caching to ASGI applications. It is powered by [`async-caches`](https://rafalp.github.io/async-caches/), and inspired by Django's cache framework.

!!! warning
    This project is in an "alpha" status. Several features still need to be implemented, and you should expect breaking API changes across minor versions.

## Features

- Compatibility with any ASGI application (e.g. Starlette, FastAPI, Quart, etc.).
- Support for application-wide or per-endpoint caching.
- Ability to fine-tune the cache behavior (TTL, cache control) down to the endpoint level.
- Clean and explicit API enabled by a loose coupling with `async-caches`.
- Fully type annotated.
- 100% test coverage.

## Installation

```bash
pip install "asgi-caches==0.*"
```

## Quickstart

```python
from asgi_caches.middleware import CacheMiddleware

cache = Cache("locmem://null")

async def app(scope, receive, send):
    assert scope["type"] == "http"
    headers = [(b"content-type", "text/plain")]
    await send({"type": "http.response.start", "status": 200, "headers": headers})
    await send({"type": "http.response.body", "body": b"Hello, world!"})

app = CacheMiddleware(app, cache=cache)
```

This example:

- Sets up an in-memory cache (see the [async-caches docs](https://rafalp.github.io/async-caches/) for specifics).
- Sets up an application (in this case, a raw-ASGI 'Hello, world!' app).
- Applies caching on the entire application.

For a deep dive into all features provided by `asgi-caches`, head to the [User Guide](/usage/)!

## Credits

Due credit goes to the Django developers and maintainers, as a lot of the API and implementation was directly inspired by the [Django cache framework](https://docs.djangoproject.com/en/2.2/topics/cache/).
