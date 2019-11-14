"""Miscellaneous utilities and helper functions."""

import base64
import email.utils
import inspect
import typing


def http_date(epoch_time: float) -> str:
    """Return a formatted date, for use in HTTP headers.

    See: https://tools.ietf.org/html/rfc7231#section-7.1.1.2
    """
    return email.utils.formatdate(epoch_time, usegmt=True)


def bytes_to_json_string(data: bytes) -> str:
    """
    Given binary data, return a string representation
    that can be safely used in a JSON object.
    """
    # NOTE: we can't just return 'data.decode()', because that won't work
    # if 'data' is not in a given encoding (e.g. utf-8), as is the case
    # when e.g. 'data' is gzip-compressed.
    return base64.encodebytes(data).decode("ascii")


def json_string_to_bytes(value: str) -> bytes:
    """
    Given a previously-computed JSON-compatible string representation of
    binary data, return the original binary data.
    """
    return base64.decodebytes(value.encode("ascii"))


def has_asgi3_signature(func: typing.Callable) -> bool:
    sig = inspect.signature(func)
    own_parameters = {name for name in sig.parameters if name != "self"}
    return own_parameters == {"scope", "receive", "send"}


def is_asgi3(app: typing.Any) -> bool:
    """Return whether 'app' corresponds to an ASGI3 callable."""
    if inspect.isclass(app):
        constructor = app.__init__  # type: ignore
        return has_asgi3_signature(constructor) and hasattr(app, "__await__")

    if inspect.isfunction(app):
        return inspect.iscoroutinefunction(app) and has_asgi3_signature(app)

    try:
        call = app.__call__
    except AttributeError:
        return False
    else:
        return inspect.iscoroutinefunction(call) and has_asgi3_signature(call)


def kvformat(**kwargs: typing.Any) -> str:
    return " ".join(f"{key}={value}" for key, value in kwargs.items())
