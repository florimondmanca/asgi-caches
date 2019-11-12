# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## 0.2.0 - 2019-11-12

### Added

- Add `@cached()` decorator. (Pull #15)

## 0.1.1 - 2019-11-12

### Added

- Add `DEBUG` and `TRACE` logs. (Pull #14)

## 0.1.0 - 2019-11-12

### Added

- Add `CacheMiddleware`. (Pull #8)
- Prevent caching of responses that have cookies when the request has none. (Pull #9)
- Prevent caching of responses if the cache TTL is zero. (Pull #10)
