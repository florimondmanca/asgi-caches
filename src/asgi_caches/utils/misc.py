"""Miscellaneous utilities and helper functions."""

import base64
import email.utils


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
