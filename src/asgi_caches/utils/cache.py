"""
Utilities that add HTTP-specific functionality to the
otherwise protocol-agnostic features in async-caches.

The `store_in_cache()` and `get_from_cache()` helpers are the main pieces of API
defined in this module:

* `store_in_cache()` learns a cache key from a `(request, response)` pair.
* `get_from_cache()` retrieves and uses this cache key for a new `request`.
"""

import hashlib
import time
import typing
from urllib.request import parse_http_list

from caches import Cache
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import Response

from ..exceptions import RequestNotCachable, ResponseNotCachable
from .logging import get_logger
from .misc import bytes_to_json_string, http_date, json_string_to_bytes

logger = get_logger(__name__)


CACHABLE_METHODS = frozenset(("GET", "HEAD"))
CACHABLE_STATUS_CODES = frozenset((200, 304))
ONE_YEAR = 60 * 60 * 24 * 365


async def store_in_cache(response: Response, *, request: Request, cache: Cache) -> None:
    """
    Given a response and a request, store the response in the cache for reuse.

    To do so, a cache key is built from:

    * The absolute URL (including query parameters)
    * Varying headers [^1], as specified specified in the "Vary" header of the response.
      These headers are stored at a key that depends only on the request URL, so that
      they can be retrieved (and checked against) for future requests (without having
      to build and read an uncached response first).

    [^1]: The "Vary" header lists which headers should be taken into account in cache
    systems, because they may result in the server sending in a different response.
    For example, gzip compression requires to add "Accept-Encoding" to "Vary" because
    sending "Accept-Encoding: gzip", and "Accept-Encoding: identity" will result in
    different responses.
    """
    if response.status_code not in CACHABLE_STATUS_CODES:
        logger.trace("response_not_cachable reason=status_code")
        raise ResponseNotCachable(response)

    if not request.cookies and "Set-Cookie" in response.headers:
        logger.trace("response_not_cachable reason=cookies_for_cookieless_request")
        raise ResponseNotCachable(response)

    if cache.ttl == 0:
        logger.trace("response_not_cachable reason=zero_ttl")
        raise ResponseNotCachable(response)

    if cache.ttl is None:
        # From section 14.12 of RFC2616:
        # "HTTP/1.1 servers SHOULD NOT send Expires dates more than
        # one year in the future."
        max_age = ONE_YEAR
        logger.trace(f"max_out_ttl value={max_age!r}")
    else:
        max_age = cache.ttl

    logger.debug(f"store_in_cache max_age={max_age!r}")

    cache_headers = get_cache_response_headers(response, max_age=max_age)
    logger.trace(f"patch_response_headers headers={cache_headers!r}")
    response.headers.update(cache_headers)

    cache_key = await learn_cache_key(request, response, cache=cache)
    logger.trace(f"learnt_cache_key cache_key={cache_key!r}")
    serialized_response = serialize_response(response)
    logger.trace(
        f"store_response_in_cache key={cache_key!r} value={serialized_response!r}"
    )
    await cache.set(key=cache_key, value=serialized_response)


async def get_from_cache(
    request: Request, *, cache: Cache
) -> typing.Optional[Response]:
    """
    Given a GET or HEAD request, retrieve a cached response based on the cache key
    associated to the request.

    If no cache key is present yet, or if there is no cached response at
    that key, return `None`.

    A `None` return value indicates that the response for this
    request can (and should) be added to the cache once computed.
    """
    logger.trace(
        f"get_from_cache "
        f"request.url={str(request.url)!r} "
        f"request.method={request.method!r}"
    )
    if request.method not in CACHABLE_METHODS:
        logger.trace("request_not_cachable reason=method")
        raise RequestNotCachable(request)

    logger.trace("lookup_cached_response method='GET'")
    # Try to retrieve the cached GET response (even if this is a HEAD request).
    cache_key = await get_cache_key(request, method="GET", cache=cache)
    if cache_key is None:
        logger.trace("cache_key found=False")
        return None
    logger.trace(f"cache_key found=True cache_key={cache_key!r}")
    serialized_response: typing.Optional[dict] = await cache.get(cache_key)

    # If not present, fallback to look for a cached HEAD response.
    if serialized_response is None:
        logger.trace("lookup_cached_response method='HEAD'")
        cache_key = await get_cache_key(request, method="HEAD", cache=cache)
        assert cache_key is not None
        logger.trace(f"cache_key found=True cache_key={cache_key!r}")
        serialized_response = await cache.get(cache_key)

    if serialized_response is None:
        logger.trace("cached_response found=False")
        return None

    logger.trace(
        f"cached_response found=True key={cache_key!r} value={serialized_response!r}"
    )
    response = deserialize_response(serialized_response)
    return response


def serialize_response(response: Response) -> dict:
    """Convert a response to JSON format.

    (This is required as `async-caches` dumps values to JSON before storing them
    in the cache system.)
    """
    return {
        "content": bytes_to_json_string(response.body),
        "status_code": response.status_code,
        "headers": dict(response.headers),
    }


def deserialize_response(serialized_response: dict) -> Response:
    """
    Given the JSON representation of a response, re-build the
    original response object.
    """
    return Response(
        content=json_string_to_bytes(serialized_response["content"]),
        status_code=serialized_response["status_code"],
        headers=serialized_response["headers"],
    )


async def learn_cache_key(request: Request, response: Response, *, cache: Cache) -> str:
    """
    Generate a cache key from the requested absolute URL.

    Varying response headers are stored at another key based from the
    requested absolute URL.
    """
    logger.trace(
        "learn_cache_key "
        f"request.method={request.method!r} "
        f"response.headers.Vary={response.headers.get('Vary')!r}"
    )
    varying_headers_cache_key = generate_varying_headers_cache_key(request, cache=cache)

    varying_headers: typing.List[str] = []
    if "Vary" in response.headers:
        for header in parse_http_list(response.headers["Vary"]):
            varying_headers.append(header.lower())
        varying_headers.sort()

    logger.trace(
        "store_varying_headers "
        f"cache_key={varying_headers_cache_key!r} headers={varying_headers!r}"
    )
    await cache.set(key=varying_headers_cache_key, value=varying_headers)

    return generate_cache_key(
        request, method=request.method, varying_headers=varying_headers, cache=cache
    )


async def get_cache_key(
    request: Request, method: str, cache: Cache
) -> typing.Optional[str]:
    """
    Given a request, return the cache key where a cached response should be looked up.
    If this request hasn't been served before, return `None` as there definitely
    won't be any matching cached response.
    """
    logger.trace(f"get_cache_key request.url={str(request.url)!r} method={method!r}")
    varying_headers_cache_key = generate_varying_headers_cache_key(request, cache=cache)
    varying_headers = await cache.get(varying_headers_cache_key)

    if varying_headers is None:
        logger.trace("varying_headers found=False")
        return None
    logger.trace(f"varying_headers found=True headers={varying_headers!r}")

    return generate_cache_key(
        request, method=method, varying_headers=varying_headers, cache=cache,
    )


def generate_cache_key(
    request: Request, method: str, varying_headers: typing.List[str], cache: Cache,
) -> str:
    """
    Return a cache key generated from the request full URL and varying
    response headers.

    Note that the given `method` may be different from that of the request, e.g.
    because we're trying to find a response cached from a previous GET request
    while this one is a HEAD request. (This is OK because web servers will strip content
    from responses to a HEAD request before sending them on the wire.)
    """
    assert method in CACHABLE_METHODS

    ctx = hashlib.md5()
    for header in varying_headers:
        value = request.headers.get(header)
        if value is not None:
            ctx.update(value.encode())

    absolute_url = str(request.url)
    url = hashlib.md5(absolute_url.encode("ascii"))

    return cache.make_key(f"cache_page.{method}.{url.hexdigest()}.{ctx.hexdigest()}")


def generate_varying_headers_cache_key(request: Request, cache: Cache) -> str:
    """
    Return a cache key generated from the requested absolute URL, suitable for
    associating varying headers to a requested URL.
    """
    url = request.url.path
    url_hash = hashlib.md5(url.encode("ascii"))
    return cache.make_key(f"varying_headers.{url_hash.hexdigest()}")


def get_cache_response_headers(
    response: Response, *, max_age: int
) -> typing.Dict[str, str]:
    """Return caching-related headers to add to a response."""
    assert max_age >= 0, "Can't have a negative cache max-age"
    headers = {}

    if "Expires" not in response.headers:
        headers["Expires"] = http_date(time.time() + max_age)

    patch_cache_control(response.headers, max_age=max_age)

    return headers


def patch_cache_control(headers: MutableHeaders, **kwargs: typing.Any) -> None:
    """
    Patch headers with an extended version of the initial Cache-Control header by adding
    all keyword arguments to it.
    """
    cache_control: typing.Dict[str, typing.Any] = {}
    for field in parse_http_list(headers.get("Cache-Control", "")):
        try:
            key, value = field.split("=")
        except ValueError:
            cache_control[field] = True
        else:
            cache_control[key] = value

    if "max-age" in cache_control and "max_age" in kwargs:
        kwargs["max_age"] = min(int(cache_control["max-age"]), kwargs["max_age"])

    if "public" in kwargs:
        raise NotImplementedError(
            "The 'public' cache control directive isn't supported yet."
        )

    if "private" in kwargs:
        raise NotImplementedError(
            "The 'private' cache control directive isn't supported yet."
        )

    for key, value in kwargs.items():
        key = key.replace("_", "-")
        cache_control[key] = value

    directives: typing.List[str] = []
    for key, value in cache_control.items():
        if value is False:
            continue
        if value is True:
            directives.append(key)
        else:
            directives.append(f"{key}={value}")

    patched_cache_control = ", ".join(directives)

    if patched_cache_control:
        headers["Cache-Control"] = patched_cache_control
    else:
        del headers["Cache-Control"]
