import logging
import os
import sys
import typing

try:  # pragma: no cover
    import click

    # Extra log info for optional coloured terminal outputs.
    HIT_EXTRA = {"color_message": "cache_lookup " + click.style("%s", fg="green")}
    MISS_EXTRA = {"color_message": "cache_lookup " + click.style("%s", fg="yellow")}
except ImportError:  # pragma: no cover
    HIT_EXTRA = {}
    MISS_EXTRA = {}


TRACE_LOG_LEVEL = 5


class Logger(logging.Logger):
    # Stub for type checkers.
    def trace(self, message: str, *args: typing.Any, **kwargs: typing.Any) -> None:
        ...  # pragma: no cover


class LoggerFactory:
    log_level_env_var = "ASGI_CACHES_LOG_LEVEL"
    log_line_format = "%(levelname)s [%(asctime)s] %(name)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    def _configure_package_logger(self, log_level: str) -> None:
        assert log_level in ("DEBUG", "TRACE")
        logger = logging.getLogger("asgi_caches")
        logger.setLevel(logging.DEBUG if log_level == "DEBUG" else TRACE_LOG_LEVEL)
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(fmt=self.log_line_format, datefmt=self.date_format)
        )
        logger.addHandler(handler)

    def get(self, name: str) -> Logger:
        """
        Get a logger instance, and optionally set up logging.
        """
        if not getattr(self, "_initialized", False):
            logging.addLevelName(TRACE_LOG_LEVEL, "TRACE")
            log_level = os.environ.get(self.log_level_env_var, "").upper()
            if log_level in ("DEBUG", "TRACE"):
                self._configure_package_logger(log_level)
            self._initialized = True

        logger = logging.getLogger(name)

        def trace(message: str, *args: typing.Any, **kwargs: typing.Any) -> None:
            logger.log(TRACE_LOG_LEVEL, message, *args, **kwargs)

        logger.trace = trace  # type: ignore

        return typing.cast(Logger, logger)


_logger_factory = LoggerFactory()
get_logger = _logger_factory.get
