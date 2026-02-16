"""
Lightweight logging setup for services.

Configures stdlib logging with timestamps and service name.
Safe for containers (logs to stdout).
"""

from __future__ import annotations

import logging
import sys


class _ServiceFormatter(logging.Formatter):
    """Formatter that injects service_name into the log record."""

    def __init__(self, service_name: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        record.service_name = getattr(record, "service_name", self._service_name)
        return super().format(record)


def setup_logging(service_name: str) -> None:
    """
    Configure root logger: timestamp + service name, stdout, INFO level.
    Idempotent for repeated calls (reconfigures handler/formatter).
    Safe for containers (stdout only).

    >>> setup_logging("test-service")
    >>> logging.getLogger().handlers
    [...]
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = _ServiceFormatter(
        service_name,
        fmt="%(asctime)s [%(levelname)s] %(service_name)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setFormatter(formatter)
