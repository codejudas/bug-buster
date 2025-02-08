import logging
import sys

from src.logging.console import ConsoleFormatter
from src.logging.kwargs_adapter import KwargsContextLoggerAdapter

ACCESS_FORMAT = "{asctime} [{levelname}] [{name}] {method} {path} {status} {time:.2f}ms {client_ip}"
LOG_FORMAT = "{asctime} [{levelname}] [{name}:{funcName}:{lineno}] - {message}"
LOG_FILE = "/var/log/easel/app.log"


def _wrapped_get_logger():
    def _inner(name: str) -> KwargsContextLoggerAdapter:
        return KwargsContextLoggerAdapter(logging.getLogger(name), {})

    return _inner


# Called once per file to get a logger for that file, automatically wraps the python logger with our special adapter
get_logger = _wrapped_get_logger()


def configure_logging(level: int = logging.INFO):
    # Reset root logger config
    logging.root.handlers = []
    logging.root.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(ConsoleFormatter(fmt=LOG_FORMAT, access_fmt=ACCESS_FORMAT, truncate_meta=True))
    stream_handler.setLevel(level)
    logging.root.addHandler(stream_handler)